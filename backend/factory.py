from .llm import CloudflareLLM


def make_llm(cache_dir=None, model=None):
    """Cloudflare Workers AI is the only provider. Raises MissingAPIKey if the credentials are not configured."""
    return CloudflareLLM(cache_dir=cache_dir, model=model)
