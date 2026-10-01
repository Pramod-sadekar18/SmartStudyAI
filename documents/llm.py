
from django.conf import settings
from google import genai


def generate_answer(question, context):
    if not settings.OPENAI_API_KEY and not settings.GEMINI_API_KEY:
        return "No AI provider is configured. Set OPEN_API_KEY or GEMINI_API_KEY."

    prompt = f"""
You are SmartStudyAI, a PDF study assistant.

Answer the user's question using only the relevant PDF context below.
Do not repeat the entire context. Return only the answer to the question.
If the context contains multiple topics, ignore unrelated topics.

If the answer is not available in the context,
say: "I could not find the answer in this PDF."

PDF Context:
{context}

Question:
{question}

Give a clear and simple answer suitable for a student.
"""

    if settings.OPENAI_API_KEY:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
            )
            answer = response.choices[0].message.content
            return (answer or "I could not find the answer in this PDF.").strip()
        except Exception as error:
            error_text = str(error).upper()
            if "401" in error_text or "403" in error_text or "API KEY" in error_text or "AUTHENTICATION" in error_text:
                return "OpenAI rejected the API key. Check OPEN_API_KEY and try again."
            if "429" in error_text or "RATE LIMIT" in error_text:
                return "OpenAI rejected the request due to a rate limit or exhausted quota. Check API usage limits and billing."
            return "OpenAI could not answer right now. Please try again."

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )
    except Exception as error:
        error_text = str(error).upper()
        if "503" in error_text or "UNAVAILABLE" in error_text:
            return "Gemini is temporarily unavailable. Please try again in a moment."
        if "401" in error_text or "403" in error_text or "API KEY" in error_text:
            return "Gemini rejected the API key. Check GEMINI_API_KEY and try again."
        return "Gemini could not answer right now. Please try again."

    return (response.text or "I could not find the answer in this PDF.").strip()