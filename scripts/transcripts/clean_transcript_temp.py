import json
import re

INPUT = "C:/Users/krist/ClaudeProjects/Jeromelu/data/transcripts/raw/UCMI4X9e8DhwpKMCQn0nQ_Ug_3hh9dXQGOcU.json"
OUTPUT = "C:/Users/krist/ClaudeProjects/Jeromelu/data/transcripts/clean/UCMI4X9e8DhwpKMCQn0nQ_Ug_3hh9dXQGOcU.json"

with open(INPUT, encoding="utf-8") as f:
    data = json.load(f)

# Corrections: (regex_pattern, replacement, description)
corrections = [
    # === Player Name Corrections ===
    (r"\bJermaine Hopgood\b", "J'maine Hopgood", "Jermaine Hopgood -> J'maine Hopgood"),
    (r"\bHopkood\b", "Hopgood", "Hopkood -> Hopgood"),
    (r"\bHobgood\b", "Hopgood", "Hobgood -> Hopgood"),
    (r"\bHopG Good\b", "Hopgood", "HopG Good -> Hopgood"),
    (r"\bhop good\b", "Hopgood", "hop good -> Hopgood"),
    (r"\bBraden Burns\b", "Braidon Burns", "Braden Burns -> Braidon Burns"),
    (r"\bSiwa Taki\b", "Siosiua Taukeiaho", "Siwa Taki -> Siosiua Taukeiaho"),
    (r"\bTaniala PCA\b", "Taniela Paseka", "Taniala PCA -> Taniela Paseka"),
    (r"\bPersa\b", "Paseka", "Persa -> Paseka"),
    (r"\bPekka\b", "Paseka", "Pekka -> Paseka"),
    (r"\bHington\b", "Hetherington", "Hington -> Hetherington"),
    (r"\bHeatherington\b", "Hetherington", "Heatherington -> Hetherington"),
    (r"\bKryton\b", "Crichton", "Kryton -> Crichton"),
    (r"\bReese Robson\b", "Reece Robson", "Reese Robson -> Reece Robson"),
    (r"\bReese Walsh\b", "Reece Walsh", "Reese Walsh -> Reece Walsh"),
    (r"\bReed Money\b", "Reed Mahoney", "Reed Money -> Reed Mahoney"),
    (r"\bread money\b", "Reed Mahoney", "read money -> Reed Mahoney"),
    (r"\bSpencer Lenu\b", "Spencer Leniu", "Spencer Lenu -> Spencer Leniu"),
    (r"\bTommy Tau\b", "Tommy Talau", "Tommy Tau -> Tommy Talau"),
    (r"\bNat Bush\b", "Nat Butcher", "Nat Bush -> Nat Butcher"),
    (r"\bMaxini\b", "Makasini", "Maxini -> Makasini"),
    (r"\bMassacini\b", "Makasini", "Massacini -> Makasini"),
    (r"\bMacini\b", "Makasini", "Macini -> Makasini"),
    (r"\bFmani\b", "Faeamani", "Fmani -> Faeamani"),
    (r"\bFamani\b", "Faeamani", "Famani -> Faeamani"),
    (r"\bIsaac Tango\b", "Izack Tago", "Isaac Tango -> Izack Tago"),
    (r"\bIsaac Tongo\b", "Izack Tago", "Isaac Tongo -> Izack Tago"),
    (r"\bCatchman\b", "Couchman", "Catchman -> Couchman"),
    (r"\bcashman\b", "Couchman", "cashman -> Couchman"),
    (r"\bBraden Tindle\b", "Braydon Trindall", "Braden Tindle -> Braydon Trindall"),
    (r"\bTrendle\b", "Trindall", "Trendle -> Trindall"),
    (r"\bSimmy Susagi\b", "Simi Sasagi", "Simmy Susagi -> Simi Sasagi"),
    (r"\bSangi\b", "Sasagi", "Sangi -> Sasagi"),
    (r"\bTimico\b", "Timoko", "Timico -> Timoko"),
    (r"\bLassard\b", "Lazarus", "Lassard -> Lazarus"),
    (r"\bLazard\b", "Lazarus", "Lazard -> Lazarus"),
    (r"\bKakamea\b", "Kamikamica", "Kakamea -> Kamikamica"),
    (r"\bKelangi\b", "Kelma Tuilagi", "Kelangi -> Kelma Tuilagi"),
    (r"\bKel Matang\b", "Kelma Tuilagi", "Kel Matang -> Kelma Tuilagi"),
    (r"\bKale Ponger\b", "Kalyn Ponga", "Kale Ponger -> Kalyn Ponga"),
    (r"\bKalen Ponga\b", "Kalyn Ponga", "Kalen Ponga -> Kalyn Ponga"),
    (r"\bVererals\b", "Verrills", "Vererals -> Verrills"),
    (r"\bStafforda\b", "Starford To'a", "Stafforda -> Starford To'a"),
    (r"\bSafeta\b", "Starford To'a", "Safeta -> Starford To'a"),
    (r"\bTailon May\b", "Taylan May", "Tailon May -> Taylan May"),
    (r"\bLuke Lai\b", "Luke Laulilii", "Luke Lai -> Luke Laulilii"),
    (r"\bSamuel Lefeno\b", "Samuela Fainu", "Samuel Lefeno -> Samuela Fainu"),
    (r"\bJake Traboy\b", "Jake Trbojevic", "Jake Traboy -> Jake Trbojevic"),
    (r"\bTom Travoyovich\b", "Tom Trbojevic", "Tom Travoyovich -> Tom Trbojevic"),
    (r"\bJosh Papi\b", "Josh Papalii", "Josh Papi -> Josh Papalii"),
    (r"\bSmidies\b", "Smithies", "Smidies -> Smithies"),
    (r"\bClearary\b", "Cleary", "Clearary -> Cleary"),
    (r"\bMax Fina\b", "Max Feagai", "Max Fina -> Max Feagai"),
    (r"\bMatt Fina\b", "Mathew Feagai", "Matt Fina -> Mathew Feagai"),
    (r"\bCoobo\b", "Cobbo", "Coobo -> Cobbo"),
    (r"\bRamian\b", "Ramien", "Ramian -> Ramien"),
    (r"\bAdam Dewey\b", "Adam Doueihi", "Adam Dewey -> Adam Doueihi"),
    (r"\bDwey\b", "Doueihi", "Dwey -> Doueihi"),
    (r"\bDewey\b", "Doueihi", "Dewey -> Doueihi"),
    (r"\bJerel Skelton\b", "Jeral Skelton", "Jerel Skelton -> Jeral Skelton"),
    (r"\bKai Pis Paul\b", "Kai Pearce-Paul", "Kai Pis Paul -> Kai Pearce-Paul"),
    (r"\bKai Pierce Paul\b", "Kai Pearce-Paul", "Kai Pierce Paul -> Kai Pearce-Paul"),
    (r"\bRyan Madison\b", "Ryan Matterson", "Ryan Madison -> Ryan Matterson"),
    (r"\bJonah Pez\b", "Jonah Pezet", "Jonah Pez -> Jonah Pezet"),
    (r"\bSen Smith\b", "Sandon Smith", "Sen Smith -> Sandon Smith"),
    (r"\bSand Smith\b", "Sandon Smith", "Sand Smith -> Sandon Smith"),
    (r"\bS and Smith\b", "Sandon Smith", "S and Smith -> Sandon Smith"),
    (r"\bFletcher Sharp\b", "Fletcher Sharpe", "Fletcher Sharp -> Fletcher Sharpe"),
    (r"\bFletcher Shark\b", "Fletcher Sharpe", "Fletcher Shark -> Fletcher Sharpe"),
    (r"\bBrayley\b", "Brailey", "Brayley -> Brailey"),
    (r"\bArama How\b", "Arama Hau", "Arama How -> Arama Hau"),
    (r"\bGreg Ingles\b", "Greg Inglis", "Greg Ingles -> Greg Inglis"),
    (r"\bJason Riy\b", "Jason Ryles", "Jason Riy -> Jason Ryles"),
    (r"\bJason Ry\b", "Jason Ryles", "Jason Ry -> Jason Ryles"),
    # === Team/NRL Term Corrections ===
    (r"\bRabbidos\b", "Rabbitohs", "Rabbidos -> Rabbitohs"),
    (r"\bParamata\b", "Parramatta", "Paramata -> Parramatta"),
    (r"\bCamber\b", "Canberra", "Camber -> Canberra"),
    (r"\bNRO\b", "NRL", "NRO -> NRL"),
    # === General fixes ===
    (r"\boneweek\b", "one-week", "oneweek -> one-week"),
    (r"\bcpped\b", "copped", "cpped -> copped"),
    (r"\bheadnock\b", "head knock", "headnock -> head knock"),
    (r"\bcapency\b", "captaincy", "capency -> captaincy"),
    (r"\bsix skin rules\b", "six again rules", "six skin rules -> six again rules"),
    (r"\bseance package\b", "severance package", "seance package -> severance package"),
    (r"\bSpotify raps\b", "Spotify Wrapped", "Spotify raps -> Spotify Wrapped"),
]

# Apply regex corrections
applied = {}
total_count = 0

for seg in data["segments"]:
    original = seg["text"]
    modified = original
    for pattern, repl, desc in corrections:
        new_text = re.sub(pattern, repl, modified)
        if new_text != modified:
            count = len(re.findall(pattern, modified))
            if desc not in applied:
                applied[desc] = 0
            applied[desc] += count
            total_count += count
            modified = new_text
    seg["text"] = modified

# Manual exact-string fixes for context-sensitive corrections
manual_fixes = [
    ("one parameter\nfront row", "one Parramatta\nfront row", "parameter -> Parramatta (context)"),
    ("one parameter front row", "one Parramatta front row", "parameter -> Parramatta (context)"),
    ("Lui back to his", "Luai back to his", "Lui -> Luai (Jarome Luai)"),
    ("Jacob Little", "Jacob Liddle", "Jacob Little -> Jacob Liddle"),
    ("with with little", "with with Liddle", "little -> Liddle (hooker context)"),
    ("see little in the", "see Liddle in the", "little -> Liddle (hooker context)"),
    ("par matter to play", "Parramatta to play", "par matter -> Parramatta"),
    ("drink water", "Drinkwater", "drink water -> Drinkwater"),
    ("Niko Clearary", "Nicho, Cleary", "Niko Clearary -> Nicho, Cleary"),
    ("40 m line", "40-metre line", "40 m line -> 40-metre line"),
    ("20 m line", "20-metre line", "20 m line -> 20-metre line"),
    ("10 me off sides", "10-metre offsides", "10 me off sides -> 10-metre offsides"),
    ("the 10 m and", "the 10-metre and", "10 m -> 10-metre"),
    ("on the buy. So that", "on the bye. So that", "buy -> bye (round context)"),
    ("the other one on\nthe buy", "the other one on\nthe bye", "buy -> bye (round context)"),
    ("the other one on the buy", "the other one on the bye", "buy -> bye (round context)"),
]

for old, new, desc in manual_fixes:
    for seg in data["segments"]:
        if old in seg["text"]:
            seg["text"] = seg["text"].replace(old, new)
            if desc not in applied:
                applied[desc] = 0
            applied[desc] += 1
            total_count += 1

# Write output
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

# Print summary
print(f"\nTotal corrections applied: {total_count}")
print("\nCorrections summary:")
print(f"{'Correction':<55} {'Count':>5}")
print("-" * 62)
for desc, count in sorted(applied.items()):
    print(f"  {desc:<53} {count:>5}")

print(f"\nOutput written to: {OUTPUT}")
