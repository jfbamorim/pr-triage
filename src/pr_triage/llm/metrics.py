import time

from openai import OpenAI

from pr_triage.domain.schemas import LLMCall


def parse_with_metrics(
    client: OpenAI,
    step: str,
    prompt_version: str,
    calls: list[LLMCall] | None,
    **kwargs,
):
    start = time.perf_counter()
    response = client.responses.parse(**kwargs)
    if calls is not None:
        usage = response.usage
        calls.append(
            LLMCall(
                step=step,
                model=kwargs["model"],
                prompt_version=prompt_version,
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                latency=time.perf_counter() - start,
            )
        )
    return response