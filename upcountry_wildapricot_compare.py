"""
Upcountry Wild Apricot ↔ Wander POI Comparison
================================================
Fetches all Wild Apricot contacts and all Wander POIs (via the export API),
fuzzy-matches them, and outputs an Excel workbook with three sheets:

  1. Matched – With Differences   — matched POIs where fields have changed
  2. Unmatched Wild Apricot        — WA contacts with no Wander POI match
  3. All Wander POIs               — full Wander export (id, external_id, metadata, etc.)

Configuration (set as environment variables or edit the CONFIG block below):
  WILDAPRICOT_API_KEY   — Wild Apricot API key
  WANDER_API_URL        — e.g. https://api.wandermaps.com
  WANDER_JWT            — Bearer token for the Wander API
  WANDER_MAP_ID         — UUID of the Upcountry SC map in prod

Usage:
  pip install requests pandas openpyxl
  python upcountry_wildapricot_compare.py
"""

import os
import sys
import base64
import difflib
import requests
import pandas as pd
from datetime import datetime

# ─── Configuration ─────────────────────────────────────────────────────────────

CONFIG = {
    "wildapricot_api_key": os.getenv("WILDAPRICOT_API_KEY", ""),
    "wander_api_url":      os.getenv("WANDER_API_URL", "https://api.wander-app.com"),
    "wander_jwt":          os.getenv("WANDER_JWT", ""),
    "wander_map_id":       os.getenv("WANDER_MAP_ID", ""),
}

# Fields to compare for differences between WA contacts and Wander POIs
COMPARE_FIELDS = ["name", "address", "website", "phone", "description"]

# Fuzzy match threshold — scores >= this are considered a match
MATCH_THRESHOLD = 85

# Output file
OUTPUT_FILE = f"upcountry_wildapricot_compare_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"


# ─── Wild Apricot API ──────────────────────────────────────────────────────────

def wa_authenticate(api_key: str) -> str:
    """Authenticate with Wild Apricot and return a Bearer token."""
    print("🔐 Authenticating with Wild Apricot...")
    auth_string = base64.b64encode(f"APIKEY:{api_key}".encode()).decode()
    resp = requests.post(
        "https://oauth.wildapricot.org/auth/token",
        headers={
            "Authorization": f"Basic {auth_string}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials", "scope": "auto", "obtain_refresh_token": "true"},
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    print("  ✅ Authenticated.")
    return token


def wa_get_account_id(token: str) -> str:
    """Fetch the Wild Apricot account ID."""
    resp = requests.get(
        "https://api.wildapricot.org/v2.2/accounts",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()[0]["Id"]


def wa_fetch_contacts(token: str, account_id: str) -> list[dict]:
    """Fetch all non-archived Wild Apricot contacts with pagination."""
    print("📥 Fetching Wild Apricot contacts...")
    base_url = f"https://api.wildapricot.org/v2.2/accounts/{account_id}/contacts"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    all_contacts = []
    skip = 0

    while True:
        resp = requests.get(base_url, headers=headers, params={
            "$async": "false", "$top": 100, "$skip": skip,
            "$filter": "IsArchived eq false",
        })
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("Contacts", [])
        all_contacts.extend(batch)
        print(f"  Page {skip // 100 + 1}: {len(batch)} contacts (total so far: {len(all_contacts)})")
        if len(batch) < 100:
            break
        skip += 100

    print(f"  ✅ {len(all_contacts)} contacts fetched.")
    return all_contacts


def wa_process_contacts(contacts: list[dict]) -> pd.DataFrame:
    """Flatten FieldValues and normalise columns."""
    processed = []
    for c in contacts:
        flat = {f["FieldName"]: f["Value"] for f in c.get("FieldValues", [])}
        c.update(flat)
        c.pop("FieldValues", None)
        processed.append(c)

    df = pd.DataFrame(processed)
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]

    # Build normalised name and address
    df["name"] = df.get("organization", df.get("first_name", "")).fillna("").astype(str)
    addr_parts = ["address1", "city", "state", "zip"]
    present = [p for p in addr_parts if p in df.columns]
    df["address"] = df[present].fillna("").agg(", ".join, axis=1).str.strip(", ")

    # Ensure key fields exist
    for col in ["website", "phone", "description"]:
        if col not in df.columns:
            df[col] = ""

    return df


# ─── Wander API ────────────────────────────────────────────────────────────────

def wander_fetch_pois(api_url: str, jwt: str, map_id: str) -> pd.DataFrame:
    """Fetch all POIs from the Wander export endpoint."""
    print("📥 Fetching Wander POIs from export API...")
    url = f"{api_url}/api/pois/map/{map_id}/export"
    resp = requests.get(url, headers={"Authorization": jwt, "Accept": "application/json"})
    resp.raise_for_status()
    data = resp.json()
    markers = data.get("markers", data) if isinstance(data, dict) else data
    df = pd.DataFrame(markers)
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
    print(f"  ✅ {len(df)} Wander POIs fetched.")
    return df


# ─── Fuzzy Matching ────────────────────────────────────────────────────────────

def fuzzy_score(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio() * 100


def find_best_match(wa_row: pd.Series, wander_df: pd.DataFrame) -> tuple[int | None, float]:
    """
    Match strategy:
      1. Exact external_id match (WA contact Id → Wander external_id) — score 100
      2. Fuzzy match on name, address, website, phone
    """
    wa_id = str(wa_row.get("id", "")).strip()

    # 1. external_id exact match
    if wa_id and "external_id" in wander_df.columns:
        exact = wander_df[wander_df["external_id"].astype(str).str.strip() == wa_id]
        if not exact.empty:
            return exact.index[0], 100.0

    # 2. Fuzzy match
    best_score, best_idx = 0.0, None
    for idx, row in wander_df.iterrows():
        score = 0.0
        for field in ["name", "address", "website", "phone"]:
            wa_val = str(wa_row.get(field, "")).strip()
            w_val  = str(row.get(field, "")).strip()
            if wa_val and w_val:
                score = max(score, fuzzy_score(wa_val, w_val))
        if score > best_score:
            best_score, best_idx = score, idx

    return best_idx, best_score


# ─── Comparison ────────────────────────────────────────────────────────────────

def compare(wa_df: pd.DataFrame, wander_df: pd.DataFrame) -> tuple[list, list]:
    """
    Returns:
      matched_with_diffs  — list of dicts for WA contacts that matched a Wander POI with field differences
      unmatched_wa        — list of dicts for WA contacts with no Wander match
    """
    matched_with_diffs = []
    unmatched_wa = []

    for _, wa_row in wa_df.iterrows():
        match_idx, score = find_best_match(wa_row, wander_df)

        if score >= MATCH_THRESHOLD and match_idx is not None:
            wander_row = wander_df.loc[match_idx]
            diffs = {}
            for field in COMPARE_FIELDS:
                wa_val  = str(wa_row.get(field, "")).strip()
                w_val   = str(wander_row.get(field, "")).strip()
                if wa_val and wa_val != w_val:
                    diffs[field] = {"wild_apricot": wa_val, "wander": w_val}

            if diffs:
                row = {
                    "match_score":          round(score, 1),
                    "match_type":           "external_id" if score == 100.0 else "fuzzy",
                    "wander_id":            wander_row.get("id", ""),
                    "wander_external_id":   wander_row.get("external_id", ""),
                    "wander_name":          wander_row.get("name", ""),
                    "wa_id":                wa_row.get("id", ""),
                    "wa_name":              wa_row.get("name", ""),
                }
                for field in COMPARE_FIELDS:
                    row[f"wa_{field}"]     = wa_row.get(field, "")
                    row[f"wander_{field}"] = wander_row.get(field, "")
                matched_with_diffs.append(row)
        else:
            closest_name = ""
            if match_idx is not None:
                closest_name = wander_df.loc[match_idx].get("name", "")
            unmatched_wa.append({
                "wa_id":              wa_row.get("id", ""),
                "wa_name":            wa_row.get("name", ""),
                "wa_address":         wa_row.get("address", ""),
                "wa_website":         wa_row.get("website", ""),
                "wa_phone":           wa_row.get("phone", ""),
                "wa_email":           wa_row.get("e-mail", wa_row.get("email", "")),
                "closest_wander_poi": closest_name,
                "closest_score":      round(score, 1),
            })

    return matched_with_diffs, unmatched_wa


# ─── Excel Output ──────────────────────────────────────────────────────────────

def write_excel(matched: list, unmatched: list, wander_df: pd.DataFrame, output_path: str):
    print(f"📊 Writing results to {output_path}...")

    # Wander POIs — keep useful columns, stringify metadata/hours
    wander_out = wander_df.copy()
    for col in ["metadata", "hours", "photos"]:
        if col in wander_out.columns:
            wander_out[col] = wander_out[col].apply(
                lambda v: str(v) if pd.notna(v) and v not in (None, "") else ""
            )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        # Sheet 1: Matched with differences
        df_matched = pd.DataFrame(matched) if matched else pd.DataFrame(columns=["(no differences found)"])
        df_matched.to_excel(writer, sheet_name="Matched – With Differences", index=False)

        # Sheet 2: Unmatched WA contacts
        df_unmatched = pd.DataFrame(unmatched) if unmatched else pd.DataFrame(columns=["(all contacts matched)"])
        df_unmatched.to_excel(writer, sheet_name="Unmatched Wild Apricot", index=False)

        # Sheet 3: Full Wander export
        wander_out.to_excel(writer, sheet_name="All Wander POIs", index=False)

        # Auto-size columns in each sheet
        for sheet in writer.sheets.values():
            for col_cells in sheet.columns:
                max_len = max((len(str(c.value or "")) for c in col_cells), default=10)
                sheet.column_dimensions[col_cells[0].column_letter].width = min(max_len + 2, 60)

    print(f"  ✅ Saved: {output_path}")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Validate config
    missing = [k for k, v in CONFIG.items() if not v]
    if missing:
        print(f"❌ Missing required config: {', '.join(missing)}")
        print("   Set them as environment variables or edit the CONFIG block at the top of this script.")
        sys.exit(1)

    # 1. Wild Apricot
    wa_token     = wa_authenticate(CONFIG["wildapricot_api_key"])
    wa_account   = wa_get_account_id(wa_token)
    wa_contacts  = wa_fetch_contacts(wa_token, wa_account)
    wa_df        = wa_process_contacts(wa_contacts)

    # 2. Wander
    wander_df = wander_fetch_pois(
        CONFIG["wander_api_url"],
        CONFIG["wander_jwt"],
        CONFIG["wander_map_id"],
    )

    # 3. Compare
    print("🔍 Running comparison...")
    matched, unmatched = compare(wa_df, wander_df)
    print(f"  Matched with differences: {len(matched)}")
    print(f"  Unmatched WA contacts:    {len(unmatched)}")
    print(f"  Total Wander POIs:        {len(wander_df)}")

    # 4. Write output
    write_excel(matched, unmatched, wander_df, OUTPUT_FILE)
    print(f"\n✅ Done! Open: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
