import os
import json
import argostranslate.package
import argostranslate.translate

# Langues depuis les variables d'environnement, avec fallback
from_code = os.environ.get("SOURCE_LANG", "fr")
to_code = os.environ.get("TARGET_LANG", "en")

# Télécharger et installer le modèle si nécessaire
argostranslate.package.update_package_index()
available_packages = argostranslate.package.get_available_packages()
package_to_install = next(
    filter(
        lambda x: x.from_code == from_code and x.to_code == to_code, available_packages
    )
)
argostranslate.package.install_from_path(package_to_install.download())

# Chemins
INPUT_DIR = os.environ.get("INPUT_DIR", "./../input")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "./../output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Boucler sur tous les fichiers .arb
for filename in os.listdir(INPUT_DIR):
    if not filename.endswith(".arb"):
        continue

    input_path = os.path.join(INPUT_DIR, filename)
    output_path = os.path.join(OUTPUT_DIR, filename)

    # Lire le fichier
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Traduire
    translated_data = {}
    for key, text in data.items():
        if key == "@@locale":
            translated_data[key] = to_code
        elif isinstance(text, str):
            translated_data[key] = argostranslate.translate.translate(text, from_code, to_code)
        else:
            translated_data[key] = text

    # Écrire le fichier traduit
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)

    print(f"{filename} traduit ✅")

print("Tous les fichiers ont été traduits ✅")
