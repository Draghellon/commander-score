from collections import defaultdict
import math
import re
import time
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Commander Data-Driven Score",
    page_icon="🧙‍♂️",
    layout="wide",
)

HEADERS = {
    "User-Agent": "CommanderWebEvaluator/3.1",
    "Accept": "application/json",
}
TOTAL_COMMANDER_CARDS = 28000.0

BRACKETS = [
    (
        0,
        99,
        "Bracket 1",
        "🪑 Chair Tribal & Bulk Bin",
        "99 cards found under a couch cushion. Zero threat, pure vibes.",
    ),
    (
        100,
        199,
        "Bracket 2",
        "📦 Fresh Out of the Cardboard Box",
        "Untouched Precon level. Winning on Turn 14 via fair combat.",
    ),
    (
        200,
        319,
        "Bracket 3",
        "🍺 Kitchen Table Beer & Pretzels",
        "Upgraded Precon. You swapped 10 taplands and feel like a genius.",
    ),
    (
        320,
        449,
        "Bracket 4",
        "📈 EDHREC Top Synergy Enjoyer",
        "Cohesive engine deck. Fair Magic, but nobody ignores your board.",
    ),
    (
        450,
        599,
        "Bracket 5",
        "🤥 'I Swear My Deck Is a 7'",
        "LGS classic: real tutors, strong engines, and 'accidental' combos.",
    ),
    (
        600,
        749,
        "Bracket 6",
        "💸 'Do You Pay the 1?'",
        "Tax collectors, free spells, fast mana. Friends sigh when they see it.",
    ),
    (
        750,
        899,
        "Bracket 7",
        "🚨 Archenemy of the Pod",
        "High-Power machine. Requires a 3v1 alliance by Turn 4 to stop you.",
    ),
    (
        900,
        1099,
        "Bracket 8",
        "🧪 Degenerate Lab Maniac",
        "Fast mana, compact combos, ruthless interaction. Blink and it's over.",
    ),
    (
        1100,
        1349,
        "Bracket 9",
        "🖨️ Printer Ink Goes Brrrr (Fringe cEDH)",
        "Optimized with Reserved List bombs, Moxen, and Turn 3 win attempts.",
    ),
    (
        1350,
        99999,
        "Bracket 10",
        "💀 Turn 1 Rhystic, Pass (Pure cEDH)",
        "Maximum tournament lethality. Zero mercy, pure competitive violence.",
    ),
]


def get_bracket_for_score(score):
    for low, high, b_num, b_title, b_desc in BRACKETS:
        if low <= score <= high:
            return b_num, b_title, b_desc, f"{low} - {high} pts"
    b_last = BRACKETS[-1]
    return b_last[2], b_last[3], b_last[4], f"{b_last[0]}+ pts"


DEFAULT_LIST = """1 Kinnan, Bonder Prodigy
1 Sol Ring
1 Arcane Signet
1 Mana Vault
1 Grim Monolith
1 Basalt Monolith
1 Mox Amber
1 Chrome Mox
1 Lotus Petal
1 Birds of Paradise
1 Delighted Halfling
1 Llanowar Elves
1 Elvish Mystic
1 Fyndhorn Elves
1 Bloom Tender
1 Rhystic Study
1 Mystic Remora
1 The One Ring
1 Consecrated Sphinx
1 Hullbreaker Horror
1 Tidespout Tyrant
1 Seedborn Muse
1 Nyxbloom Ancient
1 Nezahal, Primal Tide
1 Thassa's Oracle
1 Phyrexian Altar
1 Fierce Guardianship
1 Force of Will
1 Force of Negation
1 Mana Drain
1 Counterspell
1 Swan Song
1 Flusterstorm
1 An Offer You Can't Refuse
1 Cyclonic Rift
1 Beast Within
1 Pongify
1 Rapid Hybridization
1 Nature's Claim
1 Worldly Tutor
1 Mystical Tutor
1 Finale of Devastation
1 Green Sun's Zenith
1 Chord of Calling
1 Lightning Greaves
1 Swiftfoot Boots
1 Cultivate
1 Kodama's Reach
1 Three Visits
1 Nature's Lore
1 Gaea's Cradle
1 Ancient Tomb
1 Nykthos, Shrine to Nyx
1 Urza's Saga
1 Boseiju, Who Endures
1 Otawara, Soaring City
1 Breeding Pool
1 Tropical Island
1 Misty Rainforest
1 Polluted Delta
1 Scalding Tarn
1 Flooded Strand
1 Windswept Heath
1 Wooded Foothills
1 Verdant Catacombs
1 Command Tower
1 Exotic Orchard
1 Rejuvenating Springs
1 Yavimaya Coast
1 Barkchannel Pathway
15 Island
15 Forest"""


def parse_moxfield_deck(raw_text):
    entries = []
    counts = defaultdict(int)

    for line in raw_text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if line.lower().startswith(("sideboard", "maybeboard", "considering")):
            break

        m = re.match(r"^(\d+)x?\s+(.+)$", line)
        if m:
            qty = int(m.group(1))
            name_part = m.group(2)
        else:
            qty = 1
            name_part = line

        clean_name = re.sub(
            r"\s*\([A-Za-z0-9]+\)\s*[\dA-Za-z★†\-]+.*$", "", name_part
        )
        clean_name = re.sub(r"\s*\*.*?\*$", "", clean_name).strip()

        if " / " in clean_name and " // " not in clean_name:
            clean_name = clean_name.split(" / ")[0].strip()

        if clean_name:
            counts[clean_name] += qty
            if clean_name not in entries:
                entries.append(clean_name)

    return entries, dict(counts)


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_global_spellbook_combos(max_global_combos=1200):
    variants_list = []
    seen_ids = set()
    base_url = "https://backend.commanderspellbook.com/variants/"

    for offset in range(0, max_global_combos, 100):
        url = f"{base_url}?ordering=-popularity&limit=100&offset={offset}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception:
            continue

        for variant in data.get("results", []):
            v_id = variant.get("id")
            if v_id in seen_ids:
                continue
            seen_ids.add(v_id)
            variants_list.append(variant)
        time.sleep(0.05)

    return variants_list


def fetch_commander_specific_combos(commander_name):
    cmd_front = commander_name.split(" // ")[0]
    q_str = requests.utils.quote(cmd_front)
    base_url = "https://backend.commanderspellbook.com/variants/"
    url = f"{base_url}?q={q_str}&ordering=-popularity&limit=100"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("results", [])
    except Exception:
        pass
    return []


def fetch_cards_from_scryfall(card_names):
    cards_dict = {}
    batch_size = 25

    for i in range(0, len(card_names), batch_size):
        batch = card_names[i : i + batch_size]
        or_clauses = " or ".join([f'!"{name}"' for name in batch])
        q_str = requests.utils.quote(f"prefer:usd-low ({or_clauses})")
        url = f"https://api.scryfall.com/cards/search?q={q_str}"

        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            for card in resp.json().get("data", []):
                cards_dict[card["name"].lower()] = card
                cards_dict[card["name"].split(" // ")[0].lower()] = card
        time.sleep(0.08)

    return cards_dict


@st.cache_data(ttl=86400, show_spinner=False)
def evaluate_commander_ranks(c_name, ci_str, global_rank):
    q_raw = f"f:commander is:commander id={ci_str} prefer:usd-low sort:edhrec"
    q_str = requests.utils.quote(q_raw)
    url = f"https://api.scryfall.com/cards/search?q={q_str}"

    ci_commanders = []
    while url and len(ci_commanders) < 500:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            break
        data = resp.json()
        for c in data.get("data", []):
            if c["name"] not in ci_commanders:
                ci_commanders.append(c["name"])
        if data.get("has_more"):
            url = data.get("next_page")
            time.sleep(0.08)
        else:
            break

    total_in_ci = max(len(ci_commanders), 1)
    if c_name in ci_commanders:
        ci_rank = ci_commanders.index(c_name) + 1
    else:
        ci_rank = total_in_ci
    return ci_rank, total_in_ci


def is_resource_neutral_land(card):
    type_line = card.get("type_line", "")
    if "Basic Land" in type_line:
        return True
    if "Land" not in type_line:
        return False
    if card.get("game_changer", False):
        return False

    text = card.get("oracle_text", "").lower()
    p1 = r"add (?:(?:\{.\}){2,}|two |three |an amount |.*? for each )"
    p2 = r"\{[1-9x/wubrg]+\}, \{t\}: add \{.\}\{.\}"
    produces_multi_mana = bool(re.search(p1, text))
    if produces_multi_mana and not re.search(p2, text):
        return False
    return True


def compute_base_score(card):
    if is_resource_neutral_land(card):
        return 0.0

    rank = card.get("edhrec_rank") or int(TOTAL_COMMANDER_CARDS)
    prices = card.get("prices", {})
    price = float(prices.get("usd") or prices.get("eur") or 0.25)

    effective_price = max(0.3, min(price, 220.0) - 2.5)
    effective_rank = rank + 15.0
    s_base = 80.0 * ((effective_price / effective_rank) ** 0.65)

    if rank == 1:
        s_base = max(s_base, 50.0)

    return s_base


# ==============================================================================
# WEB INTERFACE
# ==============================================================================
st.title("🧙‍♂️ Commander Data-Driven Score & 10-Bracket System")
st.write(
    "Paste your **Moxfield** decklist below to verify legality and compute "
    "a **100% Data-Driven Power Score** based on EDHREC, Market Elasticity, "
    "and active combos from **Commander Spellbook**."
)

with st.expander("📖 View the Full 10-Bracket Scale & Score Intervals"):
    b_rows = []
    for b in BRACKETS:
        r_str = f"{b[0]} - {b[1]} pts" if b[1] < 90000 else f"{b[0]}+ pts"
        b_rows.append(
            {
                "Bracket": b[2],
                "Score Range": r_str,
                "Tier Name": b[3],
                "Description": b[4],
            }
        )
    st.table(pd.DataFrame(b_rows))

col_input1, col_input2 = st.columns([2, 1])

with col_input1:
    deck_text = st.text_area(
        "📋 Paste Moxfield Decklist (100 cards):",
        value=DEFAULT_LIST,
        height=320,
    )

with col_input2:
    parsed_names, card_counts = parse_moxfield_deck(deck_text)
    default_cmd = parsed_names[0] if parsed_names else ""
    commander_input = st.text_input(
        "👑 Commander Name (defaults to 1st card):",
        value=default_cmd,
    )
    st.info(
        "**How the Math Works:**\n"
        "- **Base Score:** $(\\text{Price} / \\text{Rank})^{0.65}$\n"
        "- **1-Mana Fixing Lands:** 0 pts\n"
        "- **Combo Multiplier:** Active ONLY if all pieces are in the deck.\n"
        "- **Commander Weight:** Multiplied **x10**."
    )
    analyze_btn = st.button(
        "🚀 Analyze Deck & Calculate Score",
        type="primary",
        use_container_width=True,
    )

if analyze_btn and parsed_names:
    with st.spinner("Scanning Scryfall and Commander Spellbook combos..."):
        if commander_input and commander_input not in parsed_names:
            parsed_names.insert(0, commander_input)
            card_counts[commander_input] = 1

        cards_dict = fetch_cards_from_scryfall(parsed_names)
        cmd_key = commander_input.lower()
        cmd_front_key = commander_input.split(" // ")[0].lower()
        cmd_card = cards_dict.get(cmd_key) or cards_dict.get(cmd_front_key)

        if not cmd_card:
            st.error(
                f"❌ Commander '{commander_input}' not found on Scryfall!"
            )
            st.stop()

        real_cmd_name = cmd_card["name"]
        cmd_ci = set(cmd_card.get("color_identity", []))
        ci_str = "".join(sorted(list(cmd_ci))).lower() if cmd_ci else "c"
        global_rank = cmd_card.get("edhrec_rank") or 5000

        # 1. LEGALITY CHECK
        total_cards_count = sum(card_counts.values())
        legality_errors = []
        not_found_cards = []

        if total_cards_count != 100:
            legality_errors.append(
                f"⚠️ Invalid Deck Size: {total_cards_count}/100 cards."
            )

        for name, qty in card_counts.items():
            c_obj = cards_dict.get(name.lower()) or cards_dict.get(
                name.split(" // ")[0].lower()
            )
            if not c_obj:
                not_found_cards.append(name)
                continue

            type_line = c_obj.get("type_line", "")
            oracle_text = c_obj.get("oracle_text", "").lower()
            is_basic = "Basic Land" in type_line
            allows_multi = (
                "a deck can have any number of cards named" in oracle_text
                or "a deck can have up to" in oracle_text
            )

            if qty > 1 and not is_basic and not allows_multi:
                legality_errors.append(
                    f"❌ Singleton Violation: '{c_obj['name']}' ({qty} copies)."
                )

            c_ci = set(c_obj.get("color_identity", []))
            if not c_ci.issubset(cmd_ci):
                legality_errors.append(
                    f"❌ Color Identity Violation: '{c_obj['name']}'."
                )

            if c_obj.get("legalities", {}).get("commander") == "banned":
                legality_errors.append(f"🚫 Banned Card: '{c_obj['name']}'.")

        # 2. COMMANDER SCORE (x10)
        ci_rank, total_in_ci = evaluate_commander_ranks(
            real_cmd_name, ci_str, global_rank
        )
        cmd_base = compute_base_score(cmd_card)
        i_ci = max(
            0.0, 1.0 - (math.log(ci_rank) / math.log(max(total_in_ci, 2)))
        )
        i_glob = max(
            0.0,
            1.0 - (math.log(global_rank) / math.log(TOTAL_COMMANDER_CARDS)),
        )
        cz_dominance_bonus = 45.0 * (i_ci * i_glob)
        cmd_raw_score = cmd_base + cz_dominance_bonus

        # 3. SCAN ACTIVE COMBOS
        cmc_lookup = {c["name"]: c.get("cmc", 3.5) for c in cards_dict.values()}
        deck_set_lower = set(cards_dict.keys()) | {
            n.lower() for n in parsed_names
        }

        raw_variants = (
            fetch_commander_specific_combos(real_cmd_name)
            + fetch_global_spellbook_combos()
        )
        seen_v_ids = set()
        active_deck_combos = []
        active_card_combos = defaultdict(list)

        for variant in raw_variants:
            v_id = variant.get("id")
            if v_id in seen_v_ids:
                continue
            seen_v_ids.add(v_id)

            uses = variant.get("uses", [])
            templates = variant.get("templates", [])
            if len(uses) < 2:
                continue

            c_names = [
                u.get("card", {}).get("name")
                for u in uses
                if isinstance(u.get("card"), dict)
                and u.get("card", {}).get("name")
            ]
            if len(c_names) < 2:
                continue

            if all(
                (
                    cn.lower() in deck_set_lower
                    or cn.split(" // ")[0].lower() in deck_set_lower
                )
                for cn in c_names
            ):
                cards_total_cmc = sum(
                    cmc_lookup.get(cn, 3.5) for cn in c_names
                ) + (len(templates) * 2.5)
                act_mana = variant.get("manaValueNeeded") or 0
                true_mana = max(cards_total_cmc, act_mana, 1)
                if true_mana > 9:
                    continue

                pop = variant.get("popularity") or 1
                produces = variant.get("produces", [])
                res_str = [
                    p.get("feature", {}).get("name", "")
                    for p in produces[:2]
                    if isinstance(p.get("feature"), dict)
                ]
                outcome = ", ".join([r for r in res_str if r]) or "Combo"
                if (
                    len(res_str) == 1
                    and "lifegain" in outcome.lower()
                    and "lose" not in outcome.lower()
                ):
                    continue

                num_pieces = len(uses) + len(templates)
                eta = math.log(1.0 + pop) / ((num_pieces**2) * true_mana)
                cmd_front_l = real_cmd_name.split(" // ")[0].lower()
                uses_cmd = any(
                    cn.lower() == real_cmd_name.lower()
                    or cn.lower() == cmd_front_l
                    for cn in c_names
                )
                effective_eta = eta * (1.5 if uses_cmd else 1.0)

                c_info = {
                    "cards": c_names,
                    "eta": effective_eta,
                    "mana": int(true_mana),
                    "outcome": outcome,
                    "uses_cmd": uses_cmd,
                }
                active_deck_combos.append(c_info)
                for cn in c_names:
                    active_card_combos[cn.lower()].append(c_info)

        cmd_combos = (
            active_card_combos.get(real_cmd_name.lower())
            or active_card_combos.get(real_cmd_name.split(" // ")[0].lower())
            or []
        )
        if cmd_combos:
            cmd_combos.sort(key=lambda x: x["eta"], reverse=True)
            cmd_harm = sum(
                c["eta"] / (idx + 1) for idx, c in enumerate(cmd_combos)
            )
            cmd_mult = 1.0 + (1.10 * cmd_harm)
        else:
            cmd_mult = 1.0

        cmd_final_score = round(cmd_raw_score * cmd_mult * 10.0, 1)

        # 4. SCORE ALL 99 CARDS
        evaluated_rows = []
        for name in parsed_names:
            c_obj = cards_dict.get(name.lower()) or cards_dict.get(
                name.split(" // ")[0].lower()
            )
            if not c_obj or c_obj["name"] == real_cmd_name:
                continue

            qty = card_counts.get(name, 1)
            s_base = compute_base_score(c_obj)
            c_combos = (
                active_card_combos.get(c_obj["name"].lower())
                or active_card_combos.get(name.lower())
                or []
            )

            if c_combos and s_base > 0:
                c_combos.sort(key=lambda x: x["eta"], reverse=True)
                harm_eta = sum(
                    c["eta"] / (idx + 1) for idx, c in enumerate(c_combos)
                )
                m_combo = 1.0 + (1.10 * harm_eta)
                best_c = c_combos[0]
                c_cards = " + ".join(best_c["cards"])
                combo_label = (
                    f"{c_cards} ({best_c['mana']} mana -> {best_c['outcome']})"
                )
            else:
                m_combo = 1.0
                combo_label = "-"

            card_score = round(s_base * m_combo, 1)
            evaluated_rows.append(
                {
                    "Card Name": c_obj["name"],
                    "Qty": qty,
                    "SCORE": card_score,
                    "Base Score": round(s_base, 1),
                    "Combo Mult": f"x{m_combo:.2f}",
                    "Game Changer": "★ YES"
                    if c_obj.get("game_changer", False)
                    else "",
                    "Min Price ($)": float(
                        c_obj.get("prices", {}).get("usd") or 0.0
                    ),
                    "EDHREC Rank": c_obj.get("edhrec_rank") or 28000,
                    "Active Combo in Deck": combo_label,
                }
            )

        evaluated_rows.sort(key=lambda x: x["SCORE"], reverse=True)
        score_99 = round(
            sum(r["SCORE"] * r["Qty"] for r in evaluated_rows), 1
        )
        total_score = round(cmd_final_score + score_99, 1)
        b_num, b_title, b_desc, b_range = get_bracket_for_score(total_score)

    st.divider()

    if not legality_errors and not not_found_cards:
        st.success(
            f"✅ Deck is Legal in Commander! ({total_cards_count}/100 cards, "
            f"Identity [{ci_str.upper()}])."
        )
    else:
        for err in legality_errors:
            st.warning(err)
        if not_found_cards:
            st.info(f"ℹ️ Unrecognized cards: {', '.join(not_found_cards)}")

    st.markdown(f"### 🎯 Assigned Tier: **{b_num} — {b_title}** *({b_range})*")
    st.caption(f"*{b_desc}*")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🏆 TOTAL DECK SCORE", f"{total_score} pts", b_num)
    m2.metric(
        "👑 Commander Score (x10)",
        f"{cmd_final_score} pts",
        f"Rank #{ci_rank}/{total_in_ci} in [{ci_str.upper()}]",
    )
    m3.metric("📚 99 Cards Score", f"{score_99} pts")
    m4.metric("⚡ Active Combos", f"{len(active_deck_combos)}")

    if active_deck_combos:
        st.subheader("⚡ Complete Combos Detected in This Deck")
        active_deck_combos.sort(key=lambda x: x["eta"], reverse=True)
        for idx, ac in enumerate(active_deck_combos, 1):
            badge = "🔥 **[USES COMMANDER]**" if ac["uses_cmd"] else "🔹"
            c_joined = " + ".join(ac["cards"])
            st.markdown(
                f"{idx}. {badge} **{c_joined}** — "
                f"*{ac['mana']} mana* $\\rightarrow$ `{ac['outcome']}`"
            )

    st.subheader("📊 Deck Cards Ranked by Score (Descending)")
    df = pd.DataFrame(evaluated_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)