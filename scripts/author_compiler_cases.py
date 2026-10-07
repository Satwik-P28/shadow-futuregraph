"""Write the compiler-study splits. Run once before any model call. Not a benchmark."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "shadowbench" / "compiler-study"


def rec(rid: str, kind: str, text: str) -> dict:
    return {"id": rid, "kind": kind, "text": text}


def case(cid: str, plan: str, records: list[dict], oracle: dict) -> dict:
    return {"id": cid, "plan_text": plan, "records": records, "oracle": oracle}


DEV = [
    case("visa_interview", "Keep Thursday morning.", [rec("cal", "calendar", "The visa interview cannot move.")], {"hard": ["cannot move"], "repair": "keep"}),
    case("sitter_email", "Get home for the handoff.", [rec("mail", "email", "You must be home before the sitter arrives.")], {"hard": ["must be home"], "repair": "keep"}),
    case("window_seat", "Pick a seat.", [rec("pref", "preference", "Alex likes a window seat when one is free.")], {"not_hard": ["window seat", "likes"], "repair": "keep"}),
    case("outside_table", "Book dinner.", [rec("pref", "preference", "Ideally the table is outside.")], {"not_hard": ["ideally", "outside"], "repair": "keep"}),
    case("closing_fight", "Sort the closing.", [rec("a", "email", "The closing cannot move."), rec("b", "email", "Please move the closing to Tuesday.")], {"hard": ["cannot move"], "contradiction": True, "repair": "keep"}),
    case("clinic_stale", "Go to the right clinic.", [rec("old", "email", "Old note: the clinic on Pine was closed."), rec("new", "reservation", "Current appointment is confirmed at the Oak clinic. This supersedes the old note.")], {"hard": ["confirmed"], "not_hard": ["closed"], "repair": "keep"}),
    case("backup_singer", "Check the quartet.", [rec("note", "message", "Nobody has said whether the backup singer is available.")], {"unknowns": ["whether"], "repair": "abstain"}),
    case("ferry_hold", "Pack for the coast.", [rec("junk", "mail", "The bicycle shop sent a spring catalog."), rec("ferry", "reservation", "The ferry booking cannot be changed.")], {"hard": ["cannot be changed"], "not_hard": ["bicycle"], "repair": "keep"}),
    case("rehearsal_pair", "Cover the afternoon.", [rec("cal", "calendar", "Jordan is speaking at 4. Sam must stay for the rehearsal.")], {"hard": ["must stay"], "repair": "keep"}),
    case("shuttle_keynote", "Catch the shuttle.", [rec("cal", "calendar", "The shuttle leaves only after the keynote ends.")], {"dependencies": ["shuttle"], "repair": "keep"}),
    case("cabin_train", "Keep the weekend hold.", [rec("res", "reservation", "The cabin hold is confirmed and is tied to the Friday train.")], {"hard": ["confirmed"], "dependencies": ["train"], "repair": "keep"}),
    case("repair_cap", "Approve the repair bill.", [rec("note", "note", "Additional spending must stay at most 40 dollars.")], {"hard": ["at most 40"], "repair": "keep"}),
    case("notary_order", "Send the packet.", [rec("note", "note", "Sign the form only after the notary finishes.")], {"dependencies": ["notary"], "repair": "keep"}),
    case("recital_fixed", "Protect Friday night.", [rec("cal", "calendar", "The recital is fixed and cannot move.")], {"hard": ["cannot move"], "repair": "keep"}),
    case("office_hours", "Shift the drop-in block.", [rec("cal", "calendar", "The office hours can move if the client agrees.")], {"not_hard": ["can move"], "repair": "keep"}),
    case("rain_portrait", "Plan the outdoor portrait.", [rec("mail", "email", "If the rain delay hits, the outdoor portrait cannot happen.")], {"hard": ["cannot happen"], "dependencies": ["rain"], "repair": "keep"}),
    case("coffee_note", "Remember the coffee.", [rec("note", "note", "Alex bought coffee on the way in.")], {"repair": "keep"}),
    case("studio_airport", "Be in both places.", [rec("a", "calendar", "Be in the studio at 9."), rec("b", "calendar", "Be at the airport at 9.")], {"contradiction": True, "unknowns": ["studio"], "repair": "abstain"}),
    case("vague_deadline", "What is due?", [rec("note", "note", "A deadline exists somewhere in the thread.")], {"unknowns": ["deadline"], "repair": "abstain"}),
    case("friday_maybe", "Look at Friday.", [rec("msg", "message", "The thing on Friday might need to happen.")], {"not_hard": ["might"], "unknowns": ["might"], "repair": "abstain"}),
    case("already_held", "Leave the booking alone.", [rec("res", "reservation", "The reservation is already confirmed. No change is needed.")], {"hard": ["confirmed"], "repair": "keep"}),
    case("kindergarten", "Guard the morning tour.", [rec("mail", "email", "Do not cancel the kindergarten tour.")], {"hard": ["do not cancel"], "repair": "keep"}),
    case("cake_doors", "Time the delivery.", [rec("mail", "email", "Mom wrote that the cake has to arrive before the doors open.")], {"hard": ["before the doors"], "repair": "keep"}),
    case("later_train", "Think about the ride home.", [rec("pref", "preference", "Maybe a later train would be nicer.")], {"not_hard": ["maybe", "later train"], "repair": "keep"}),
    case("pet_lease", "Decide about the dog.", [rec("lease", "email", "The lease says pets are banned."), rec("room", "message", "The roommate says the dog can stay.")], {"hard": ["banned"], "contradiction": True, "repair": "keep"}),
    case("gate_notice", "Find the gate.", [rec("old", "message", "Yesterday's text said the gate was B12."), rec("new", "email", "The airline notice says this supersedes that text: the gate is not confirmed.")], {"unknowns": ["not confirmed"], "not_hard": ["B12"], "repair": "abstain"}),
    case("fare_gap", "Check the change fee.", [rec("mail", "email", "The fare change amount is not confirmed.")], {"unknowns": ["not confirmed"], "repair": "abstain"}),
    case("review_pair", "Set the review.", [rec("cal", "calendar", "Priya's review cannot move. Chris can skip the review.")], {"hard": ["cannot move"], "not_hard": ["can skip"], "repair": "keep"}),
    case("hotel_flight", "Keep the room.", [rec("res", "reservation", "The hotel room is held only if the flight stays on Thursday.")], {"dependencies": ["flight"], "repair": "keep"}),
    case("shared_cap", "Stay inside the cap.", [rec("note", "note", "The shared repair cap is a maximum additional 75 dollars.")], {"hard": ["maximum additional 75"], "repair": "keep"}),
    case("signature_mail", "Send it in order.", [rec("note", "note", "Mail the contract after the signature, not before.")], {"dependencies": ["signature"], "repair": "keep"}),
    case("anniversary", "Protect the evening.", [rec("cal", "calendar", "The anniversary dinner is fixed.")], {"hard": ["fixed"], "repair": "keep"}),
]

TEST = [
    case("deposition", "Hold the morning.", [rec("cal", "calendar", "The deposition cannot be rescheduled.")], {"hard": ["cannot be rescheduled"], "repair": "keep"}),
    case("keys_noon", "Return the keys.", [rec("mail", "email", "The landlord wrote that you must return the keys before noon.")], {"hard": ["must return"], "repair": "keep"}),
    case("quiet_car", "Choose a carriage.", [rec("pref", "preference", "Alex prefers the quiet car.")], {"not_hard": ["prefers", "quiet car"], "repair": "keep"}),
    case("exit_row", "Sit somewhere.", [rec("pref", "preference", "Perhaps sit near the exit.")], {"not_hard": ["perhaps"], "repair": "keep"}),
    case("board_vote", "Prepare the vote.", [rec("a", "email", "The board vote cannot move."), rec("b", "email", "Please move the board vote to Monday.")], {"hard": ["cannot move"], "contradiction": True, "repair": "keep"}),
    case("warehouse", "Ship from the live site.", [rec("old", "email", "Old note: the warehouse on 3rd was vacated."), rec("new", "reservation", "Current pickup is confirmed at the dock. This supersedes the old note.")], {"hard": ["confirmed"], "not_hard": ["vacated"], "repair": "keep"}),
    case("photographer", "Book the portraits.", [rec("note", "message", "Nobody has said whether the photographer can make the Saturday slot.")], {"unknowns": ["whether"], "repair": "abstain"}),
    case("recital_mail", "Sort the mail pile.", [rec("junk", "mail", "A seed catalog arrived from the garden store."), rec("cal", "calendar", "The spring recital cannot move.")], {"hard": ["cannot move"], "not_hard": ["seed catalog"], "repair": "keep"}),
    case("two_sets", "Staff the evening.", [rec("cal", "calendar", "Mina must run the sound check. Leo can leave after the opener.")], {"hard": ["must run"], "not_hard": ["can leave"], "repair": "keep"}),
    case("bus_lecture", "Make the bus.", [rec("cal", "calendar", "The campus bus departs only after the lecture ends.")], {"dependencies": ["lecture"], "repair": "keep"}),
    case("cottage_ferry", "Hold the cottage.", [rec("res", "reservation", "The cottage is confirmed and depends on the afternoon ferry.")], {"hard": ["confirmed"], "dependencies": ["ferry"], "repair": "keep"}),
    case("extra_spend", "Buy the supplies.", [rec("note", "note", "Spend no more than 25 dollars extra.")], {"hard": ["no more than 25"], "repair": "keep"}),
    case("appeal_stamp", "File the appeal.", [rec("note", "note", "File the appeal after the clerk stamps it.")], {"dependencies": ["clerk"], "repair": "keep"}),
    case("baptism", "Keep Sunday morning.", [rec("cal", "calendar", "The baptism is fixed and cannot move.")], {"hard": ["cannot move"], "repair": "keep"}),
    case("brainstorm", "Nudge the workshop.", [rec("cal", "calendar", "The brainstorm can move to the following week.")], {"not_hard": ["can move"], "repair": "keep"}),
    case("kiln_power", "Schedule the firing.", [rec("note", "note", "A power cut would stop the kiln, so the firing depends on the power staying up.")], {"dependencies": ["power"], "repair": "keep"}),
    case("watered_plant", "Note the plant.", [rec("note", "note", "The plant was watered this morning.")], {"repair": "keep"}),
    case("noon_clash", "Make both noon commitments.", [rec("a", "calendar", "Meet the client at noon."), rec("b", "reservation", "Be on the noon train out of the city.")], {"contradiction": True, "unknowns": ["noon"], "repair": "abstain"}),
    case("something_due", "What should I finish?", [rec("note", "note", "Something important is due, but the note never says what.")], {"unknowns": ["something important"], "repair": "abstain"}),
    case("friday_busy", "Read the text.", [rec("msg", "message", "Friday could be busy, or it could be nothing.")], {"not_hard": ["could"], "unknowns": ["could"], "repair": "abstain"}),
    case("tickets_done", "Leave the tickets.", [rec("res", "reservation", "The tickets are already confirmed. Leave them as they are.")], {"hard": ["confirmed"], "repair": "keep"}),
    case("oath", "Be there for the oath.", [rec("mail", "email", "Do not miss the oath at the courthouse.")], {"hard": ["do not miss"], "repair": "keep"}),
    case("caterer", "Time the trays.", [rec("mail", "email", "The caterer said the trays must be there before guests sit.")], {"hard": ["must be there"], "repair": "keep"}),
    case("lab_badge", "Keep the badge slot.", [rec("cal", "calendar", "The lab badge appointment is fixed and cannot move.")], {"hard": ["cannot move"], "repair": "keep"}),
]


def main() -> None:
    if (ROOT / "test" / "FROZEN.sha256").exists():
        raise SystemExit("test split is frozen; refusing to rewrite cases")
    for split, rows in (("dev", DEV), ("test", TEST)):
        folder = ROOT / split
        folder.mkdir(parents=True, exist_ok=True)
        cases = [{"id": row["id"], "plan_text": row["plan_text"], "records": row["records"]} for row in rows]
        oracle = {}
        for row in rows:
            item = {
                "hard": row["oracle"].get("hard") or [],
                "not_hard": row["oracle"].get("not_hard") or [],
                "dependencies": row["oracle"].get("dependencies") or [],
                "not_dependencies": row["oracle"].get("not_dependencies") or [],
                "unknowns": row["oracle"].get("unknowns") or [],
                "repair": row["oracle"].get("repair"),
                "contradiction": bool(row["oracle"].get("contradiction")),
            }
            oracle[row["id"]] = item
        (folder / "cases.json").write_text(json.dumps(cases, indent=2) + "\n")
        (folder / "oracle.json").write_text(json.dumps(oracle, indent=2) + "\n")
    print(f"dev {len(DEV)} test {len(TEST)}")


if __name__ == "__main__":
    main()
