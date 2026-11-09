"""Sort every employer into the GeoCareers branches ("Branchen entdecken").

The `sector` column holds 1-2 of the branches below (main one first), joined with " / ".
Values that are already branches are kept, so your own edits stay. Anything else (old sector
labels, free text from research) is converted using the old label, the company name and the
description (`eng`).
"""
import re

# English value stored in the workbook -> German label shown on the site
BRANCHES = {
    "Renewable Energy": "Erneuerbare Energien",
    "Development & Social": "Entwicklung & Soziales",
    "Climate": "Klima",
    "Surveying & Geodesy": "Vermessung & Geodäsie",
    "Environment & Conservation": "Umwelt & Naturschutz",
    "GIS": "GIS",
    "Geoinformatics": "Geoinformatik",
    "Remote Sensing": "Fernerkundung",
    "Hydrology": "Hydrologie",
    "Geology": "Geologie",
    "Transport Planning": "Verkehrsplanung",
    "Urban & Spatial Planning": "Stadtplanung & Raumplanung",
    "Other": "Weitere",
}

# keywords per branch: (pattern, weight). Old sector labels count 3, name 2, description 1.
KEYWORDS = {
    "Renewable Energy": r"renewable|erneuerbar|solar|photovolt|\bpv\b|wind|hydrogen|wasserstoff|biogas|energiewende|"
                        r"energy transition|energy|energie|strom|power grid|stromnetz|netzbetreiber|grid operator|utilit",
    "Climate": r"climate|klima|carbon|co2|emission|heat ?island|hitze|adaptation",
    "Development & Social": r"development cooperation|entwicklungszusammenarbeit|international development|humanitar|"
                            r"\bngo\b|non-profit|nonprofit|social|sozial|giz\b|kfw|health|gesundheit|census|demograph",
    "Surveying & Geodesy": r"survey|vermess|geodes|geodä|cadast|kataster|liegenschaft|laser ?scan|photogrammetr|"
                           r"mobile mapping|total station|tachymet|öbvi|gnss|3d scan|point cloud|punktwolke",
    "Environment & Conservation": r"environment|umwelt|nature|natur|landscape|landschaft|biodivers|ecolog|ökolog|forest|"
                                  r"wald|agricultur|landwirt|conservation|species|arten|noise|lärm|contaminat|altlast",
    "GIS": r"\bgis\b|esri|arcgis|qgis|mapping|kartograph|cartograph|geodata service|location data|location intelligence|"
           r"geospatial service|geodaten",
    "Geoinformatics": r"software|platform|plattform|developer|data science|machine learning|\bai\b|artificial intellig|"
                      r"digital twin|digitaler zwilling|spatial data infrastructure|\bsdi\b|geodateninfrastruktur|"
                      r"web ?mapping|saas|analytics|geoinformati|\btech\b|it services|it-dienst",
    "Remote Sensing": r"earth observation|erdbeobachtung|satellite|satellit|remote sensing|fernerkund|\bsar\b|"
                      r"aerial|luftbild|orthophoto|drone|drohne|uav|hyperspectral|imagery",
    "Hydrology": r"hydro(?!gen)|water|wasser|flood|hochwasser|drainage|entwässer|sewer|abwasser|river|fluss|"
                 r"groundwater|grundwasser|coastal|küste|maritime|hafen|port authority",
    "Geology": r"geolog|geotechn|geophysi|baugrund|subsurface|untergrund|mining|bergbau|raw material|rohstoff|"
               r"soil|boden|drilling|bohr",
    "Transport Planning": r"mobility|mobilität|transport|traffic|verkehr|rail|bahn|logistic|road|straße|strasse|"
                          r"public transport|öpnv|shipping|freight|airport|flughafen|navigation|routing|automotive",
    "Urban & Spatial Planning": r"urban|stadtplan|städtebau|regional plan|raumplan|raumordnung|land use|flächennutz|"
                                r"bauleitplan|real estate|immobil|architect|architekt|city development|stadtentwickl|"
                                r"municipal|kommun|smart city|property|liegenschaft",
}
_RX = {b: re.compile(p, re.I) for b, p in KEYWORDS.items()}


def is_branch_value(value):
    parts = [p.strip() for p in str(value or "").split("/") if p.strip()]
    return bool(parts) and all(p in BRANCHES for p in parts)


def classify(sector, name="", description=""):
    """Return 1-2 branches joined with ' / '."""
    if is_branch_value(sector):
        return " / ".join(p.strip() for p in str(sector).split("/") if p.strip())
    scores = {}
    for text, weight in ((sector, 3), (name, 2), (description, 1)):
        text = str(text or "")
        for b, rx in _RX.items():
            hits = len(set(m.lower() for m in rx.findall(text)))
            if hits:
                scores[b] = scores.get(b, 0) + weight * hits
    if not scores:
        return "Other"
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top = [ranked[0][0]]
    if len(ranked) > 1 and ranked[1][1] >= max(2, 0.6 * ranked[0][1]):
        top.append(ranked[1][0])
    return " / ".join(top)


CODES = {i: b for i, b in enumerate(BRANCHES, 1)}      # 1 = Renewable Energy ... 13 = Other


def apply_updates(spec):
    """spec: JSON {"berlin:1": "6+11", ...} (sheet:id -> branch numbers). Writes the sectors into the workbook."""
    import json
    from . import excel
    updates = json.loads(spec)
    frames = excel.read_city_sheets()
    n = 0
    for sheet, df in frames.items():
        for idx, row in df.iterrows():
            try:
                code = updates.get(f"{sheet}:{int(row['id'])}")
            except (TypeError, ValueError):
                continue
            if code:
                df.at[idx, "sector"] = " / ".join(CODES[int(c)] for c in str(code).split("+"))
                n += 1
    excel.write_city_sheets(frames)
    print(f"[branchen] set the branch of {n} employers")


if __name__ == "__main__":
    import os
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "apply":
        spec = os.environ.get("SECTOR_UPDATES", "").strip()
        if spec:
            apply_updates(spec)
        else:
            print("[branchen] no updates given")
    else:
        sys.exit(__doc__)
