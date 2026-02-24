# 🤖 Word Bomb Assistant (FR Only, Instant Response)
![Platform](https://img.shields.io/badge/Platform-Windows-0A66FF?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OCR](https://img.shields.io/badge/OCR-EasyOCR-1F2937?style=for-the-badge)
![Language](https://img.shields.io/badge/Dictionary-FR_Only-16A34A?style=for-the-badge)
Bot ultra-rapide pour le jeu **Word Bomb**, utilisant OCR pour détecter les lettres et répondre instantanément avec des noms communs français uniquement.

---

# ✨ Fonctionnalités

* 🇫🇷 Français uniquement
* 📖 Utilise uniquement des **noms communs**
* 🚫 Filtre les **prénoms, marques et noms propres**
* ⚡ Réponse **quasi instantanée (5 ms)**
* 👁️ OCR automatique avec EasyOCR
* 🎯 Détection automatique du fragment à l’écran
* ⌨️ Écriture et envoi automatiques
* 🧠 Dictionnaire intelligent (200 000 mots)

---

# ⌨️ Raccourcis

| Touche | Action                  |
| ------ | ----------------------- |
| F8     | Démarrer/arreter le bot |
| F9     | Quitter                 |

---

# 📦 Installation

## 1. Installer Python

Python 3.10 ou supérieur recommandé
https://www.python.org/downloads/

---

## 2. Installer les dépendances

Dans le dossier du bot :

```bash
pip install -r requirements.txt
```

---

## 3. Lancer le bot

```bash
python wordbomb_bot.py
```

---

# 📁 Structure des fichiers

```
wordbomb_bot/
│
├── wordbomb_bot.py
├── blocked_names.txt
├── extra_words.txt
├── requirements.txt
└── README.md
```

---

# 🚫 blocked_names.txt

Liste noire personnalisée.

Exemple :

```
google
youtube
amazon
nike
adidas
paris
macron
```

Ces mots ne seront jamais utilisés.

---

# ➕ extra_words.txt

Ajoute tes propres mots.

Exemple :

```
ordinateur
clavier
voiture
maison
```

---

# ⚙️ Fonctionnement

Le bot :

1. Capture la zone du jeu
2. Détecte les lettres avec OCR
3. Cherche un mot valide
4. Écrit instantanément
5. Appuie sur ENTER

Temps total : **< 10 ms**

---

# 🧠 Source des mots

Utilise la base de données :

* wordfreq
* filtrée
* nettoyée
* normalisée
* blacklist appliquée

---

# 🎯 Optimisations

* aucune latence
* aucune temporisation
* frappe directe
* sélection intelligente
* filtrage anti noms propres

---

# 🛑 Important

Clique sur la fenêtre du jeu avant d'activer le bot.

---

# 🖥️ Compatibilité

* Windows ✅
* Linux ✅
* macOS (pas testé demerde toi) ❌

---

# ⚠️ Disclaimer

Usage éducatif uniquement tqt

---

# 📈 Performance

| Action        | Temps  |
| ------------- | ------ |
| OCR           | 2-8 ms |
| Recherche mot | <1 ms  |
| Écriture      | 0 ms   |
| Total         | ~5 ms  |

---

# 🧩 Dépendances

* easyocr
* keyboard
* mss
* numpy
* wordfreq

---

# ⭐ Tips

Pour performance maximale :

* utiliser résolution 1080p
* fermer les applications inutiles

---

# ✅ Prêt à jouer

Démarre avec F8 et laisse le bot tout faire.
