"""
RAG Setup für RezeptAgent — Ingestion Phase
=============================================
Liest alle Rezepte aus data/recipes/*.md ein, erstellt Embeddings
mit BAAI/bge-m3 (das du bereits kennst!) und speichert alles in ChromaDB.

Einmalig ausführen:
    python app/rag/rag_setup.py
"""

import os
import chromadb
from sentence_transformers import SentenceTransformer


# ─── Konfiguration ────────────────────────────────────────────────────────────

RECIPES_DIR   = "data/recipes"          # Ordner mit deinen .md Rezeptdateien
CHROMA_PATH   = "data/chroma"           # Wo ChromaDB gespeichert wird
COLLECTION    = "rezepte"               # Name der Collection
EMBEDDING_MODEL = "BAAI/bge-m3"        # Du kennst dieses Modell schon!

# ─── Modell & DB laden ────────────────────────────────────────────────────────

print(f"Lade Embedding-Modell: {EMBEDDING_MODEL} ...")
model = SentenceTransformer(EMBEDDING_MODEL)

client = chromadb.PersistentClient(path=CHROMA_PATH)

# Collection neu erstellen (oder bestehende löschen + neu anlegen)
# Bei erneutem Ausführen: alte Collection löschen um Duplikate zu vermeiden
try:
    client.delete_collection(name=COLLECTION)
    print("Alte Collection gelöscht.")
except Exception:
    pass

collection = client.create_collection(name=COLLECTION)
print(f"Collection '{COLLECTION}' erstellt in {CHROMA_PATH}")


# ─── Rezepte einlesen ─────────────────────────────────────────────────────────

def read_recipes(folder_path: str) -> tuple[list[str], list[dict], list[str]]:
    """
    Liest alle .md Dateien aus dem Ordner ein.
    Gibt texte, metadaten und ids zurück.
    """
    texte, metadaten, ids = [], [], []

    if not os.path.exists(folder_path):
        print(f"[!] Ordner '{folder_path}' nicht gefunden. Erstelle Beispielrezepte...")
        _create_example_recipes(folder_path)

    for i, filename in enumerate(sorted(os.listdir(folder_path))):
        if not filename.lower().endswith(".md"):
            continue

        filepath = os.path.join(folder_path, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read().strip()

            if not text:
                print(f"[!] Leer übersprungen: {filename}")
                continue

            texte.append(text)
            metadaten.append({"filename": filename, "filepath": filepath})
            ids.append(f"rezept_{i+1:04d}")
            print(f"[✓] Eingelesen: {filename}")

        except Exception as e:
            print(f"[!] Fehler bei {filename}: {e}")

    return texte, metadaten, ids


# ─── Embeddings erstellen & speichern ─────────────────────────────────────────

texte, metadaten, ids = read_recipes(RECIPES_DIR)

if not texte:
    print("[!] Keine Rezepte gefunden. Bitte Rezepte in data/recipes/ ablegen.")
else:
    print(f"\nErstelle Embeddings für {len(texte)} Rezept(e)...")
    embeddings = model.encode(texte, show_progress_bar=True)

    collection.add(
        documents=texte,
        embeddings=embeddings,
        metadatas=metadaten,
        ids=ids,
    )
    print(f"\n[✓] {len(texte)} Rezepte erfolgreich in ChromaDB gespeichert!")
    print(f"    Pfad: {CHROMA_PATH}")
    print(f"    Collection: {COLLECTION}")


# ─── Beispielrezepte erstellen (falls noch keine vorhanden) ───────────────────

def _create_example_recipes(folder_path: str):
    """Erstellt 5 Beispielrezepte damit du sofort loslegen kannst."""
    os.makedirs(folder_path, exist_ok=True)

    rezepte = {
        "pasta_tomaten.md": """# Pasta mit Tomatensauce

**Zutaten (2 Personen):**
- 200g Spaghetti
- 400g gehackte Tomaten (Dose)
- 2 Knoblauchzehen
- 1 Zwiebel
- Olivenöl, Salz, Pfeffer, Basilikum

**Zubereitung:**
1. Zwiebel und Knoblauch fein hacken und in Olivenöl anschwitzen
2. Tomaten dazugeben, 15 Minuten köcheln lassen
3. Mit Salz, Pfeffer und Basilikum würzen
4. Pasta al dente kochen und mit der Sauce vermischen

**Zeit:** 25 Minuten | **Schwierigkeit:** Einfach
**Tags:** pasta, vegetarisch, schnell, tomaten, italienisch
""",

        "haehnchensuppe.md": """# Hähnchen-Gemüsesuppe

**Zutaten (4 Personen):**
- 2 Hähnchenbrustfilets
- 3 Karotten
- 2 Selleriestangen
- 1 Zwiebel
- 1,5l Hühnerbrühe
- Petersilie, Salz, Pfeffer

**Zubereitung:**
1. Hähnchen in der Brühe 20 Minuten kochen, herausnehmen und zerpflücken
2. Gemüse in Würfel schneiden und in die Brühe geben
3. 15 Minuten köcheln lassen
4. Hähnchen wieder dazu, mit Petersilie garnieren

**Zeit:** 45 Minuten | **Schwierigkeit:** Einfach
**Tags:** suppe, hähnchen, gesund, warm, winter
""",

        "caesar_salat.md": """# Caesar Salat

**Zutaten (2 Personen):**
- 1 Römersalat
- 100g Parmesan
- 100g Croutons
- 2 EL Caesar-Dressing
- Schwarzer Pfeffer

**Zubereitung:**
1. Salat in mundgerechte Stücke zupfen und waschen
2. Dressing über den Salat träufeln und vermischen
3. Croutons und Parmesan-Hobel dazugeben
4. Frisch pfeffern und sofort servieren

**Zeit:** 10 Minuten | **Schwierigkeit:** Sehr einfach
**Tags:** salat, vegetarisch, schnell, kalt, amerikanisch, frisch
""",

        "risotto_pilze.md": """# Pilzrisotto

**Zutaten (2 Personen):**
- 200g Risotto-Reis (Arborio)
- 300g gemischte Pilze
- 1 Zwiebel
- 150ml Weißwein
- 800ml Gemüsebrühe
- 50g Parmesan, Butter, Olivenöl

**Zubereitung:**
1. Zwiebel glasig anschwitzen, Reis dazugeben und kurz rösten
2. Mit Weißwein ablöschen
3. Brühe nach und nach einrühren, ständig rühren (20 Min.)
4. Pilze separat anbraten und unterheben
5. Mit Butter und Parmesan verfeinern

**Zeit:** 35 Minuten | **Schwierigkeit:** Mittel
**Tags:** risotto, pilze, vegetarisch, cremig, italienisch, aufwendig
""",

        "avocado_toast.md": """# Avocado Toast

**Zutaten (1 Person):**
- 2 Scheiben Sauerteigbrot
- 1 reife Avocado
- 1 Zitrone
- Chiliflocken, Salz, Pfeffer
- Optional: Ei (Spiegelei oder pochiert)

**Zubereitung:**
1. Brot toasten
2. Avocado mit Zitronensaft, Salz und Pfeffer zerdrücken
3. Auf das Brot streichen
4. Mit Chiliflocken bestreuen
5. Optional: Ei obendrauf legen

**Zeit:** 10 Minuten | **Schwierigkeit:** Sehr einfach
**Tags:** toast, avocado, frühstück, schnell, vegetarisch, trendy
""",
    }

    for filename, inhalt in rezepte.items():
        with open(os.path.join(folder_path, filename), "w", encoding="utf-8") as f:
            f.write(inhalt)
        print(f"[✓] Beispielrezept erstellt: {filename}")
