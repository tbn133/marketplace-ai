"""Entry point — ties planner, executor, and evaluator together."""

from __future__ import annotations

from pathlib import Path

from config import AppConfig, load_config, validate_tools
from evaluator import evaluate
from executor import execute
from planner import plan


def run(input: dict) -> dict:
    """Run the AI voice cover pipeline.

    Input:
        {"url": "string", "voice": "string", "style": "string | auto"}

    Output:
        {
            "best_audio": "string",
            "versions": ["string"],
            "meta": {"style": "string", "params": {}}
        }
    """
    url = input.get("url", "")
    voice = input.get("voice", "")
    style = input.get("style", "auto")

    if not url:
        return {"error": "Missing 'url' in input."}
    if not voice:
        return {"error": "Missing 'voice' in input."}

    # Load config and validate
    config = load_config()
    errors = validate_tools(config)
    if errors:
        return {"error": "Tool validation failed.", "details": errors}

    # Resolve styles.yaml path (same directory as this file)
    styles_path = Path(__file__).parent / "styles.yaml"

    # Plan
    plan_result = plan(style=style, voice=voice, styles_path=styles_path)

    # Execute
    exec_result = execute(
        url=url,
        voice=voice,
        plan_result=plan_result,
        config=config,
    )

    # Evaluate
    versions_for_eval = [{"path": str(v.path)} for v in exec_result.versions]
    eval_result = evaluate(
        versions=versions_for_eval,
        ffprobe_path=config.tools.ffprobe_path,
    )

    return {
        "best_audio": str(eval_result.best),
        "versions": [str(v.path) for v in exec_result.versions],
        "meta": {
            "style": plan_result.style,
            "params": {
                "blend_values": plan_result.blend_values,
                "pitch_shift": plan_result.pitch_shift,
                "formant_shift": plan_result.formant_shift,
            },
            "title": exec_result.metadata.get("title", ""),
            "evaluation": eval_result.reason,
        },
    }
