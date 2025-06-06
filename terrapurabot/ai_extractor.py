import os
import json
import openai
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

# Get the API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logger.error("API key not found. Check your .env file.")
    exit(1)

# Initialize the OpenAI client
client = openai.OpenAI(api_key=api_key)


def find_empty_fields(data):
    empties = []

    # Top-level fields in Herb
    herb = data.get("Herb", {})
    if not herb.get("Name", "").strip():
        empties.append("Herb.Name")
    if not herb.get("LatinName", "").strip():
        empties.append("Herb.LatinName")
    if not herb.get("Description", "").strip():
        empties.append("Herb.Description")
    if not herb.get("Dosage", "").strip():
        empties.append("Herb.Dosage")
    if not herb.get("Tags"):
        empties.append("Herb.Tags")
    if not herb.get("Sources", "").strip():
        empties.append("Herb.Sources")

    # AilmentsTreated
    ailments = herb.get("AilmentsTreated", [])
    if not ailments or not ailments[0].get("Name", "").strip():
        empties.append("Herb.AilmentsTreated[0].Name")
    if not ailments or not ailments[0].get("Description", "").strip():
        empties.append("Herb.AilmentsTreated[0].Description")

    # SideEffects
    effects = herb.get("SideEffects", [])
    if not effects or not effects[0].get("Name", "").strip():
        empties.append("Herb.SideEffects[0].Name")
    if not effects or not effects[0].get("Description", "").strip():
        empties.append("Herb.SideEffects[0].Description")
    if not effects or not effects[0].get("Severity", "").strip():
        empties.append("Herb.SideEffects[0].Severity")

    # HerbPreparationSteps
    steps = data.get("HerbPreparationSteps", [])
    if not steps or not steps[0].get("StepName", "").strip():
        empties.append("HerbPreparationSteps[0].StepName")
    if not steps or not steps[0].get("Description", "").strip():
        empties.append("HerbPreparationSteps[0].Description")
    if not steps or not steps[0].get("Duration", "").strip():
        empties.append("HerbPreparationSteps[0].Duration")
    if not steps or not steps[0].get("Temperature", "").strip():
        empties.append("HerbPreparationSteps[0].Temperature")
    if not steps or not steps[0].get("Type", "").strip():
        empties.append("HerbPreparationSteps[0].Type")
    if not steps or not steps[0].get("Order"):
        empties.append("HerbPreparationSteps[0].Order")

    # HerbWarnings
    warnings = data.get("HerbWarnings", [])
    if not warnings or not warnings[0].get("WarningTitle", "").strip():
        empties.append("HerbWarnings[0].WarningTitle")
    if not warnings or not warnings[0].get("Description", "").strip():
        empties.append("HerbWarnings[0].Description")
    if not warnings or not warnings[0].get("WarningType", "").strip():
        empties.append("HerbWarnings[0].WarningType")
    if not warnings or not warnings[0].get("Order"):
        empties.append("HerbWarnings[0].Order")

    # ScientificStudies
    studies = data.get("ScientificStudies", [])
    if not studies or not studies[0].get("StudyTitle", "").strip():
        empties.append("ScientificStudies[0].StudyTitle")
    if not studies or not studies[0].get("Summary", "").strip():
        empties.append("ScientificStudies[0].Summary")
    if not studies or not studies[0].get("DOI", "").strip():
        empties.append("ScientificStudies[0].DOI")
    if not studies or not studies[0].get("ExternalLink", "").strip():
        empties.append("ScientificStudies[0].ExternalLink")

    # Tags
    tags = data.get("Tags", [])
    if not tags or not tags[0].get("Name", "").strip():
        empties.append("Tags[0].Name")

    return empties


def extract_herb_info_with_gpt(entry):
    latin = entry.get("latin_name", "").strip()
    text_pfaf = entry.get("textpfaf", "").strip()
    text_webmd = entry.get("textwebmd", "").strip()
    text_herbpathy = entry.get("textherbpathy", "").strip()

    if not text_pfaf or "error" in text_pfaf.lower() or "not found" in text_pfaf.lower():
        logger.warning(f"Skipping {latin} — invalid or missing PFAF content.")
        logger.debug(text_pfaf)
        return None

    # --- STEP 1: Generate base JSON from PFAF only ---
    prompt1 = f"""
You are a herbal medicine expert AI.  
Using ONLY this PFAF data, fill out the JSON below.  
Leave any unknown fields blank.

PFAF:
{text_pfaf}

Return ONLY valid JSON in this structure:
{{
  "Herb": {{
    "Name": "",
    "LatinName": "{latin}",
    "Description": "",
    "Dosage": "",
    "Tags": [],
    "Sources": "",
    "AilmentsTreated": [{{"Name": "","Description": ""}}],
    "SideEffects": [{{"Name": "","Description": "","Severity": "mild"}}]
  }},
  "HerbPreparationSteps":[{{"StepName": "","Description": "","Duration": "","Temperature": "","Type": "","Order": 1}}],
  "HerbWarnings":[{{"WarningTitle": "","Description": "","WarningType": "","Order": 1}}],
  "ScientificStudies":[{{"StudyTitle": "","Summary": "","DOI": "","ExternalLink": ""}}],
  "Tags":[{{"Name": ""}}]
}}
"""

    try:
        response1 = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful herbal medicine assistant."},
                {"role": "user", "content": prompt1}
            ],
            temperature=0.2,
            max_tokens=1000
        )

        result1 = response1.choices[0].message.content.strip().strip("```json").strip("```")
        data = json.loads(result1)

    except Exception as e:
        logger.error(f"Error in initial PFAF parsing for {latin}: {e}")
        logger.debug("Raw GPT response:\n%s", result1)
        return None

    # --- STEP 2: Check for empty fields ---
    empty_fields = find_empty_fields(data)

    if empty_fields and (text_webmd or text_herbpathy):
        logger.info(f"Filling missing fields from WebMD/Herbpathy")
        source_texts = ""
        if text_webmd:
            source_texts += f"\n--- WebMD ---\n{text_webmd}"
        if text_herbpathy:
            source_texts += f"\n--- Herbpathy ---\n{text_herbpathy}"

        prompt2 = f"""
Some fields are missing in this herb JSON: {", ".join(empty_fields)}.  
Use the following text to fill ONLY those missing fields.

INSTRUCTIONS:
1. First, try to extract information from the text below.
2. If the text does NOT contain the information, use your own trusted and up-to-date herbal medicine knowledge.
3. If a field already has data but more relevant info is available, APPEND the new info.
4. DO NOT leave any of the listed fields blank.
5. DO NOT change any fields that already have data.
6. OUTPUT a valid, complete JSON with the missing fields filled.

TEXT:
{source_texts}

Current JSON (fill missing fields only):
{json.dumps(data, indent=2)}
"""

        try:
            response2 = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful herbal medicine assistant."},
                    {"role": "user", "content": prompt2}
                ],
                temperature=0.3,
                max_tokens=1000
            )

            result2 = response2.choices[0].message.content.strip().strip("```json").strip("```")
            data = json.loads(result2)

        except Exception as e:
            logger.error(f"Error filling missing fields for {latin}: {e}")
            logger.debug("Raw GPT response:\n%s", result2)
            return data  # Return partial result anyway

    return data
