"""The 9-stage pipeline executor."""
from __future__ import annotations

from gatent.core.diff import Differ
from gatent.core.router import Router
from gatent.core.templates import DEFAULT_TEMPLATE, render_template
from gatent.core.types import (
    AwaitingApproval,
    PipelineContext,
    RunRecord,
    SinkError,
    SkipModule,
)


async def execute_pipeline(ctx: PipelineContext, record: RunRecord) -> None:
    """Run all 9 stages against the context. Mutates record + ctx."""
    engine = ctx.engine
    module = ctx.module

    # Stage 1: TRIGGER (already fired)
    record.stage_started("trigger")
    ctx.trigger = ctx.trigger_payload
    record.stage_ended("trigger")

    # Stage 2: AUTH
    record.stage_started("auth")
    if module.auth_profile_id:
        ctx.auth = await engine.vault.load_credentials(module.auth_profile_id, module)
    record.stage_ended("auth")

    # Stage 3: NAVIGATE
    record.stage_started("navigate")
    runner = engine.registry.resolve_runner(module, engine.profile.default_runner)
    ctx.navigation_result = await runner.navigate(module, ctx)
    record.stage_ended("navigate")

    # Stage 4: EXTRACT
    record.stage_started("extract")
    extract_type = module.config["extract"]["type"]
    extractor = engine.registry.resolve_extractor(extract_type)
    ctx.raw_records = await extractor.extract(module, ctx)
    record.stage_ended("extract")

    if not ctx.raw_records:
        raise SkipModule("No records extracted")

    # Stage 5: TRANSFORM
    record.stage_started("transform")
    for op in module.config.get("transform", []):
        transformer = engine.registry.resolve_transformer(op["operation"])
        ctx.raw_records = await transformer.apply(op, ctx.raw_records, ctx)
    record.stage_ended("transform")

    # Stage 6: DIFF
    record.stage_started("diff")
    differ = Differ(module.config["diff"], engine.state_store)
    ctx.events = await differ.compute(ctx.raw_records, module.module_id, ctx.run_id)
    record.stage_ended("diff")
    record.events_emitted = len(ctx.events)

    if not ctx.events:
        return  # nothing changed

    await engine.state_store.write_events(ctx.events)

    # Stage 7: ROUTE
    record.stage_started("route")
    router = Router(module.config["route"])
    ctx.routed = router.route(ctx.events)
    record.stage_ended("route")

    # Stage 8: SINK
    record.stage_started("sink")
    for entry in ctx.routed:
        for sink_name in entry.sinks:
            sink_config = module.config["sinks"][sink_name]
            sink = engine.registry.resolve_sink(sink_config)
            try:
                await sink.write(entry.event, sink_config, ctx)
                record.sinks_succeeded += 1
            except SinkError as e:
                record.sinks_failed += 1
                # Log via engine (TODO: pluggable logger)
                print(f"[gatent] Sink {sink_name} failed: {e}")
    record.stage_ended("sink")

    # Stage 9: NOTIFY
    record.stage_started("notify")
    for entry in ctx.routed:
        if entry.requires_approval:
            raise AwaitingApproval(entry)
        for notifier_name in entry.notifiers:
            notifier_config = module.config["notifiers"][notifier_name]
            notifier = engine.registry.resolve_notifier(notifier_config)
            template = (
                module.config.get("notify_templates", {}).get(entry.template_name)
                or DEFAULT_TEMPLATE
            )
            rendered = render_template(template, {"event": entry.event.to_dict()})
            try:
                await notifier.send(rendered, entry.severity, notifier_config)
            except Exception as e:
                print(f"[gatent] Notifier {notifier_name} failed: {e}")
    record.stage_ended("notify")
