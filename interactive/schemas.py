"""Shared schemas and controlled vocabularies for the local explorer."""

KEY = ["prompt_id", "prompt_language", "model"]
LANGUAGES = ["en", "zh", "ar", "ru", "hi"]
LANGUAGE_LABELS = {
    "en": "English", "zh": "Chinese", "ar": "Arabic",
    "ru": "Russian", "hi": "Hindi",
}
MODEL_JURISDICTION = {
    "deepseek-chat-v3.1": "CN", "glm-4.7-flash": "CN",
    "hunyuan-a13b": "CN", "kimi-k2.5": "CN", "qwen3-max": "CN",
    "allam-7b": "MENA", "falcon3-10b": "MENA", "jais-8b": "MENA",
    "sarvam-30b": "India", "sarvam-105b": "India",
    "krutrim-2-instruct-local-q8": "India",
    "claude-opus-4.5": "US", "gemini-2.5-flash-lite": "US",
    "gpt-4o": "US", "gpt-5.1": "US", "grok-4.3": "US",
    "llama-4-scout": "US", "nova-lite": "US",
    "ministral-14b": "EU", "mistral-large-2512": "EU",
    "bielik-11b-v3.0": "EU", "eurollm-22b-instruct-2512-local-q8": "EU",
    "salamandra-7b-instruct-2606-local-q8": "EU",
    "gigachat3-10b-a1.8b-local-q8": "Russia",
}
VALIDITY_CLASSES = [
    "coherent answer", "genuine refusal", "coherent pivot",
    "incoherent-garbled", "wrong-language", "technical degeneration",
    "ambiguous",
]
COLOUR_FIELDS = {
    "Overall non-engagement propensity": "refusal_propensity_all",
    "Selected-language propensity": "selected_language_propensity",
    "Selected-model non-engagement": "selected_model_refusal",
    "Genuine-refusal propensity": "genuine_refusal_propensity",
    "Capability-failure propensity": "capability_failure_propensity",
    "Judge disagreement": "judge_disagreement_propensity",
}
