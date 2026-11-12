#!/usr/bin/env python3
"""Build the Persian-front version of the Communication en dialogues deck."""

import csv
import io
import json
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "packs/fr/dataset"
SOURCE = DATASET / "decks/comm-dial-a2b1-phrases.json"
OUTPUT = DATASET / "decks/comm-diag-a2b1-fa-fr.json"
MANIFEST = DATASET / "manifest.json"
REMOTE_CSV_OUTPUT = DATASET / "csv/Comm_diag_a2b1.csv"

DECK_ID = "comm-diag-a2b1-fa-fr"
DECK_NAME = "Comm_diag_a2b1 · FA→FR"
EXPECTED_SOURCE_ROWS = 1354
EXPECTED_UNIQUE_FRONTS = 1343

CHAPTER_TITLES = {
    "01": "INVITER, ACCEPTER, REFUSER, S’EXCUSER",
    "02": "OFFRIR, REMERCIER",
    "03": "ANNONCER UN ÉVÉNEMENT, FÉLICITER",
    "04": "DEMANDER UN SERVICE, DONNER UN CONSEIL",
    "05": "RASSURER, ENCOURAGER, FAIRE UN REPROCHE",
    "06": "AU RESTAURANT, À L’HÔTEL",
    "07": "PARLER D’ARGENT",
    "08": "PARLER DE SA SANTÉ",
    "09": "SE DÉPLACER EN VILLE, EN TRAIN, EN AVION",
    "10": "LES LOISIRS ET LES VACANCES",
    "11": "EXPRIMER UN BESOIN, UNE ENVIE, UN DÉSIR",
    "12": "EXPRIMER UN SOUHAIT, UN ESPOIR, UN PROJET",
    "13": "EXPRIMER DES DIFFICULTÉS, DES CRAINTES",
    "14": "EXPRIMER SES SENTIMENTS",
    "15": "EXPRIMER SON ADMIRATION, SA DÉCEPTION",
    "16": "PRÉSENTER SON PARCOURS PROFESSIONNEL",
    "17": "PRENDRE OU SE RENDRE À UN RENDEZ-VOUS",
    "18": "FAIRE UNE INSCRIPTION",
    "19": "DEMANDER DES INFORMATIONS",
    "20": "DÉPOSER UNE PLAINTE, UNE RÉCLAMATION",
    "21": "EXPRIMER SON OPINION",
    "22": "CONTESTER, NIER, INSISTER",
    "23": "FAIRE UNE CRITIQUE SUR UNE ŒUVRE",
    "24": "DÉFENDRE UNE CAUSE",
}

# These alternatives are interchangeable in the source context; other slash-separated
# forms are retained as alternatives without labelling them as synonyms.
SYNONYMS = {
    "à condition que + subjonctif": ("à condition que + subjonctif", ["pourvu que + subjonctif"]),
    "à condition que + subj.": ("à condition que + subjonctif", ["pourvu que + subjonctif"]),
    "décaler / repousser un dîner": ("décaler un dîner", ["repousser un dîner"]),
    "Je partage ton chagrin / ta peine": ("Je partage ton chagrin", ["Je partage ta peine"]),
    "Pas de problème / Sans souci": ("Pas de problème", ["Sans souci"]),
    "faire un drame / un plat / une montagne de qqch": (
        "faire un drame",
        ["en faire un plat", "faire toute une montagne de quelque chose"],
    ),
    "en faire un fromage / un plat": ("en faire un fromage", ["en faire un plat"]),
    "la tune / le fric / les ronds / les sous / l’oseille": (
        "la tune",
        ["le fric", "les sous"],
    ),
    "la tune / le fric / les ronds / les sous / l'oseille": (
        "la tune",
        ["le fric", "les sous"],
    ),
    "Je n'ai plus un rond / un sou": ("Je n'ai plus un rond", ["Je n'ai plus un sou"]),
    "avoir la pêche / la frite / la patate": ("avoir la pêche", ["avoir la frite", "avoir la patate"]),
    "avoir de la fièvre / de la température": ("avoir de la fièvre", ["avoir de la température"]),
    "s'évanouir / perdre connaissance": ("s'évanouir", ["perdre connaissance"]),
    "planifier / programmer": ("planifier", ["programmer"]),
    "prévoir / projeter": ("prévoir", ["projeter"]),
    "un job / du taf": ("un job", ["du taf"]),
    "craindre / redouter": ("craindre", ["redouter"]),
    "rassembler / réunir les documents": ("rassembler les documents", ["réunir les documents"]),
    "piquer une crise / une colère": ("piquer une crise", ["piquer une colère"]),
    "Je m'en fiche / Je m'en moque": ("Je m'en fiche", ["Je m'en moque"]),
    "bûcher / potasser / bachoter": ("bûcher", ["potasser", "bachoter"]),
    "sécher / louper / manquer un cours": (
        "sécher un cours",
        ["louper un cours", "manquer un cours"],
    ),
    "Bien entendu / Évidemment": ("Bien entendu", ["Évidemment"]),
    "C'est incontestable / indéniable": ("C'est incontestable", ["C'est indéniable"]),
    "Tu fais erreur / tu as tort": ("Tu fais erreur", ["Tu as tort"]),
    "un opposant / un détracteur": ("un opposant", ["un détracteur"]),
    "en premier lieu / (tout) d'abord": ("en premier lieu", ["tout d'abord"]),
    "ensuite / en second lieu": ("ensuite", ["en second lieu"]),
    "enfin / pour finir": ("enfin", ["pour finir"]),
    "en réalité / en fait / à vrai dire": ("en réalité", ["en fait", "à vrai dire"]),
    "puisque / car / parce que": ("puisque", ["car", "parce que"]),
    "afin de / en vue de + inf.": ("afin de", ["en vue de + infinitif"]),
    "afin que / pour que + subj.": ("afin que", ["pour que + subjonctif"]),
    "malgré / en dépit de": ("malgré", ["en dépit de"]),
    "cependant / néanmoins / pourtant": ("cependant", ["néanmoins", "pourtant"]),
    "bien que / quoique + subj.": ("bien que", ["quoique + subjonctif"]),
    "mis à part / excepté": ("mis à part", ["excepté"]),
    "bref / en somme": ("bref", ["en somme"]),
}

EXAMPLES = {
    "Cela vous tenterait ?": "Un dîner au restaurant, cela vous tenterait ?",
    "Pourquoi pas !": "— On prend un café ? — Pourquoi pas !",
    "Nous avons le plaisir de vous annoncer...": "Nous avons le plaisir de vous annoncer l’ouverture de notre agence.",
    "Tu pourrais me dépanner ?": "Tu pourrais me dépanner en gardant mon chat ce week-end ?",
    "Auriez-vous l'amabilité de m'aider ?": "Auriez-vous l'amabilité de m'aider à porter cette valise ?",
    "De quoi s'agit-il ?": "De quoi s'agit-il exactement ?",
    "Vous avez choisi ?": "Vous avez choisi ? Je peux prendre votre commande ?",
    "Qu'est-ce qui vous ferait plaisir ?": "Qu'est-ce qui vous ferait plaisir en dessert ?",
    "Et pour la cuisson ?": "Et pour la cuisson de votre steak ?",
    "Les chiens sont-ils admis ?": "Les chiens sont-ils admis dans cet hôtel ?",
    "N'allez pas si vite !": "N'allez pas si vite, je ne peux pas suivre.",
    "Comment tu te sens ?": "Comment tu te sens aujourd'hui ?",
    "Quel optimisme !": "Quel optimisme ! Tu penses vraiment qu'on va gagner ?",
    "Tu me fais envie avec ta glace !": "Tu me fais envie avec ta glace, j'en prendrais bien une aussi.",
    "Pourvu que ça marche !": "J'ai envoyé ma candidature. Pourvu que ça marche !",
    "Ça se voit tant que ça ?": "Je suis fatigué ? Ça se voit tant que ça ?",
    "C'est intolérable !": "Cette attente est intolérable !",
    "De quels documents dois-je me munir ?": "De quels documents dois-je me munir pour l'inscription ?",
    "À partir de quand est-il possible de s'inscrire ?": "À partir de quand est-il possible de s'inscrire ?",
    "Ça, c'est bien parlé !": "Tu as défendu ton point de vue avec calme. Ça, c'est bien parlé !",
    "Qu'est-ce que tu en penses ?": "La proposition est intéressante. Qu'est-ce que tu en penses ?",
    "Tu crois que ça en vaut la peine ?": "Le trajet est long. Tu crois que ça en vaut la peine ?",
    "Tu exagères !": "Tu exagères ! Ce n'était qu'un petit retard.",
}


def front_from_bilingual_meaning(meaning: str) -> str:
    english, separator, persian = meaning.rpartition(" / ")
    assert separator and english.strip() and persian.strip(), f"Expected English / Persian meaning: {meaning!r}"
    assert any("\u0600" <= char <= "\u06ff" for char in persian), f"Missing Persian text: {meaning!r}"
    return persian.strip()


def french_back(source_word: str) -> str:
    if source_word in SYNONYMS:
        main, synonyms = SYNONYMS[source_word]
        return main + "\nSynonymes : " + "; ".join(synonyms[:2])
    return source_word.replace(" / ", " ; ")


def make_cards(source_rows: list[dict]) -> list[dict[str, str]]:
    missing_examples = {row["w"] for row in source_rows if not row.get("s", "").strip()}
    assert missing_examples == set(EXAMPLES), f"Fallback example coverage changed: {missing_examples ^ set(EXAMPLES)}"

    grouped: OrderedDict[str, dict] = OrderedDict()
    for row in source_rows:
        unit = row.get("l", "").strip()
        assert unit in CHAPTER_TITLES, f"Unknown unit: {unit!r}"
        front = front_from_bilingual_meaning(row.get("m", ""))
        entry = grouped.setdefault(front.casefold(), {"w": front, "meanings": [], "examples": [], "units": []})
        meaning = french_back(row["w"].strip())
        if meaning not in entry["meanings"]:
            entry["meanings"].append(meaning)

        example = row.get("s", "").strip() or EXAMPLES[row["w"]]
        unit_label = f"Unité {unit} — {CHAPTER_TITLES[unit]}"
        entry["examples"].append(example)
        if unit_label not in entry["units"]:
            entry["units"].append(unit_label)

    cards = []
    for entry in grouped.values():
        meanings = entry["meanings"]
        meaning = meanings[0]
        for other in meanings[1:]:
            meaning += "\nAutre équivalent : " + other.replace("\n", " — ")
        meaning += "\n\n" + "\n".join(entry["units"])
        examples = list(dict.fromkeys(entry["examples"]))
        sentence = "\n\n".join(examples)
        cards.append({"w": entry["w"], "m": meaning, "s": sentence})
    return cards


def validate(source_rows: list[dict], cards: list[dict[str, str]]) -> None:
    assert len(source_rows) == EXPECTED_SOURCE_ROWS
    assert len(cards) == EXPECTED_UNIQUE_FRONTS
    assert len({card["w"].casefold() for card in cards}) == len(cards)
    units = {f"Unité {number:02d} — {title}" for number, title in enumerate(CHAPTER_TITLES.values(), 1)}
    seen_units = {unit for card in cards for unit in units if unit in card["m"]}
    assert seen_units == units
    assert all(any("\u0600" <= char <= "\u06ff" for char in card["w"]) for card in cards)
    assert all(card["m"].strip() and "/" not in card["m"] for card in cards)
    assert all(card["s"].strip() and "Unité " not in card["s"] for card in cards)
    assert all(any(unit in card["m"] for unit in units) for card in cards)


def main() -> None:
    source_rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    cards = make_cards(source_rows)
    validate(source_rows, cards)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    deck_bytes = (json.dumps(cards, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    OUTPUT.write_bytes(deck_bytes)

    csv_file = io.StringIO(newline="")
    writer = csv.writer(csv_file, lineterminator="\n")
    writer.writerow(["word", "meaning", "sentence", "deck"])
    writer.writerows([card["w"], card["m"], card["s"], DECK_NAME] for card in cards)
    csv_text = csv_file.getvalue()
    parsed_csv = list(csv.reader(io.StringIO(csv_text, newline="")))
    assert len(parsed_csv) == len(cards) + 1
    assert all(row[3] == DECK_NAME for row in parsed_csv[1:])
    assert len({row[0].casefold() for row in parsed_csv[1:]}) == len(cards)
    for csv_path in (REMOTE_CSV_OUTPUT,):
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8", newline="") as csv_output:
            csv_output.write(csv_text)

    deck = {
        "id": DECK_ID,
        "name": DECK_NAME,
        "level": "A2-B1",
        "kind": "phrases",
        "file": "decks/comm-diag-a2b1-fa-fr.json",
        "count": len(cards),
        "sizeBytes": len(deck_bytes),
    }
    for manifest_path in (MANIFEST,):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["version"] = max(manifest["version"], 4)
        manifest["decks"] = [item for item in manifest["decks"] if item["id"] != DECK_ID] + [deck]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Generated {len(cards)} unique cards from {len(source_rows)} source rows; {deck['sizeBytes']} bytes.")


if __name__ == "__main__":
    main()
