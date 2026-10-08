# Semantic Failure Analysis

This analysis uses the ten development cases in `shadowbench/semantic-explore/cases.json` and the final product-parity Super run captured by `scripts/semantic_parity.py`. The runner used the product context shape, record ID `user`, `compile_semantic`, explicit model `nvidia/nemotron-3-super-120b-a12b`, strict grounding, obligation coverage, and repair evaluation. No frozen benchmark artifact was changed.

The final run cost `$0.0047511`, averaged `1.797s` per case, produced `3/10` executable worlds, `0` premise rejections, `0` false-safe decisions, `7` unnecessary abstentions, and `0` non-keep repairs.

## Case Findings

### A

**Input:** My professor moved Thursday's lab to finish at 4:15. I need to pick up my sister when her practice ends at 5. The drive normally takes 25 to 45 minutes. Can I stop for groceries on the way?

**Raw proposal:** Facts: `lab_finish` (`finish at 4:15` -> `4:15`), `practice_end` (`pick up my sister when her practice ends at 5` -> `5`), `drive_duration` (`The drive normally takes 25 to 45 minutes` -> `25 to 45 minutes`). Link: `can_stop_groceries`, `sum_before`, inputs `[lab_finish, drive_duration]`, deadline `practice_end`, quote `Can I stop for groceries on the way?`.

**Omitted:** The grocery stop has no duration or relationship premise. The proposal treats the route without the requested stop as complete.

**Rejected:** None. **Unresolved obligations:** None after the current inventory classification. **Status:** `EXECUTABLE`; expected `NEEDS_INFORMATION`. **Repair:** No non-keep repair. **Classification:** `MODEL_OMISSION` and `OBLIGATION_COVERAGE_FAILURE`. The model omitted a material duration, and the independent inventory does not yet connect a natural-language stop request to a missing duration strongly enough.

### B

**Input:** My flight lands at 6:20, but my dinner reservation is at 7:30. It usually takes half an hour to get out of the airport and another 20 to 50 minutes to reach the restaurant.

**Raw proposal:** Facts: `flight_lands`, `dinner_reservation`, `airport_exit_duration`, `travel_to_restaurant_duration`. Link: `total_travel_time`, `sum_before`, inputs `[flight_lands, airport_exit_duration, travel_to_restaurant_duration]`, deadline `dinner_reservation`.

**Omitted:** None material. **Rejected:** None. **Unresolved obligations:** None. **Status:** `EXECUTABLE`; expected `EXECUTABLE`. Baseline decision is feasible at the low end and fails at the high end. **Repair:** No non-keep repair was grounded. **Classification:** No compilation failure; `REPAIR_FAILURE` for the absence of a grounded alternative.

### C

**Input:** I've got $450 left for discretionary spending this month. I already committed $180 to a birthday present. I'm considering buying headphones for $210 and concert tickets for $125.

**Raw proposal:** Facts: `discretionary_budget`, `birthday_commitment`, `headphones_considering`, `concert_tickets_considering`. No links. **Rejected:** None. **Unresolved obligations:** Two budget-related candidates. **Status:** `NEEDS_INFORMATION`; expected `EXECUTABLE`.

**Omitted:** The `sum_at_most` budget relationship. Optionality was present in the source wording but not converted into an executable action. **Repair:** No repair because no budget constraint or grounded drop action was created. **Classification:** `MODEL_OMISSION` and `MISSING_ACTION`.

### D

**Input:** I need to leave work by 4 to make my dentist appointment. My manager just scheduled a meeting that ends at 4:30. That meeting cannot be moved.

**Raw proposal:** Facts: `leave_work` (`need to leave work by 4` -> `4`), `meeting_end` (`meeting that ends at 4:30` -> `4:30`). No links. Unknown: `travel time from work/meeting location to dentist`.

**Omitted:** The direct temporal conflict between a required departure at 4 and a fixed meeting ending at 4:30. **Rejected:** None. **Unresolved obligations:** One. **Status:** `NEEDS_INFORMATION`; expected `EXECUTABLE` for conflict detection. **Repair:** None, correctly because no authorized alternative was supplied. **Classification:** `MODEL_OMISSION`; the model omitted a relationship that can be evaluated from the stated hard facts.

### E

**Input:** My friend wants dinner around seven, but she hasn't confirmed the reservation.

**Raw proposal:** Fact: `dinner_time` (`around seven` -> `around seven`). No links. Unknowns: exact dinner time and whether dinner is fixed or confirmed.

**Omitted:** None material. **Rejected:** None. **Status:** `NEEDS_INFORMATION`; expected `NEEDS_INFORMATION`. **Repair:** Not applicable. **Classification:** Correct abstention.

### F

**Input:** My calendar says the interview is at 2, but the recruiter's newer email says 3. I'm not sure whether the calendar invitation was updated.

**Raw proposal:** Facts: `calendar_time` and `email_time`. Contradiction: `time_conflict`, `two_stated_times_same_event_no_supersede`. No links.

**Omitted:** None material. **Rejected:** None. **Status:** `CONTRADICTORY`; expected `CONTRADICTORY`. **Repair:** Not permitted without a confirmed source. **Classification:** Correct contradiction handling.

### G

**Input:** My partner needs the car from 3 until 6. I was planning to drive to the airport at 4.

**Raw proposal:** Facts: `partner_car_need_start`, `partner_car_need_end`, `planned_drive_time`. No links. Unknown: driving duration is not stated.

**Omitted:** The shared-resource overlap relationship. The model correctly did not invent a drive duration, but it treated the planned use as a time point and did not emit a resource identity or overlap relation. **Rejected:** None. **Unresolved obligations:** One. **Status:** `NEEDS_INFORMATION`; expected `EXECUTABLE` for resource conflict detection. **Repair:** None; no alternative car or authorized change was stated. **Classification:** `MODEL_OMISSION` and `ENTITY_RESOLUTION_ERROR` risk, because the resource was not represented as a grounded shared car entity.

### H

**Input:** I have to get to a wedding by 5, and my train arrives at 4:15.

**Raw proposal:** Facts: `wedding_deadline`, `train_arrival`. No links. Unknown: travel time from station to venue.

**Omitted:** No relationship can be safely evaluated because the transfer duration is absent. **Rejected:** None. **Unresolved obligations:** One. **Status:** `NEEDS_INFORMATION`; expected `NEEDS_INFORMATION`. **Repair:** Not applicable. **Classification:** Correct abstention.

### I

**Input:** If it rains, the ceremony moves indoors and starts half an hour earlier.

**Raw proposal:** Fact: `ceremony_start_rain` (`starts half an hour earlier` -> `half an hour earlier`). No links. Unknowns: normal ceremony start and absolute rainy-day start.

**Omitted:** None that can be safely grounded without an original start time. **Rejected:** None. **Status:** `NEEDS_INFORMATION`; expected `NEEDS_INFORMATION`. **Repair:** Not applicable. **Classification:** Correct abstention; relative-time parsing remains intentionally incomplete.

### J

**Input:** My class ends at 3:30. The drive to the station takes 15-35 minutes, the train leaves at 4:10, and parking takes another 5-12 minutes.

**Raw proposal:** Facts: `class_end`, `drive_duration`, `train_departure`, `parking_duration`. Link: `can_catch_train`, `sum_before`, inputs `[class_end, drive_duration, parking_duration]`, deadline `train_departure`. The quote contains a shortened multi-premise explanation, but all operand facts are grounded.

**Omitted:** None material. **Rejected:** None after premise-based relationship validation. **Unresolved obligations:** None. **Status:** `EXECUTABLE`; expected `EXECUTABLE`. **Repair:** No non-keep repair. **Classification:** Correct executable world; high-end failure is discovered by deterministic evaluation.

## Root-Cause Distribution

Counts are non-exclusive because one case can contain multiple failures.

| Classification | Count | Cases |
|---|---:|---|
| `MODEL_OMISSION` | 4 | A, C, D, G |
| `PROMPT_SCHEMA_MISMATCH` | 0 | None observed after parity routing |
| `SOURCE_GROUNDING_ERROR` | 0 | No final-run rejected facts or links |
| `NUMERIC_PARSING_ERROR` | 0 | No final-run numeric rejection |
| `ENTITY_RESOLUTION_ERROR` | 1 risk | G; resource identity was not represented |
| `UNSUPPORTED_RELATION` | 0 | None |
| `MISSING_ACTION` | 1 | C; optional purchase action was not emitted |
| `REPAIR_FAILURE` | 2 executable cases | B and J had no non-keep repair; their failures are temporal boundary failures without supplied alternatives |
| `OBLIGATION_COVERAGE_FAILURE` | 2 | A and C; material request/budget obligations were not connected to relationships |

The dominant remaining cause is model reasoning and relationship emission, not source-ID alignment or quote validation. The deterministic grounding change removed the measured false rejection in J without permitting unsupported evidence.

## Comparison

The historical product-parity Super run before these changes was `3/10` executable, with one relationship quote rejection and `7` unnecessary abstentions. The final run remained `3/10` executable because model output varied, but relationship rejection fell to `0`; the run exposed 4 model omissions and 7 unnecessary abstentions. The controlled five-case comparison remains: Lightning `0/5` executable, Super `2/5` executable.

The final ten-case run had `0` false-safe and `0` false-unsafe decisions. It had no verified sandbox execution; repair evaluation did not produce a grounded non-keep action.

## Safety Assessment

No source validation was weakened. Unknown source IDs remain rejected. Duration and money normalization only accepts semantically equivalent parsed values; ambiguous clock conversions are not normalized. Incomplete worlds remain non-approvable, and the existing authorization, stale-contract, provider-verification, and session-isolation protections were not bypassed.

## Next Priority

Do not add another compiler abstraction. Improve Super's structured emission for optional budget actions and direct hard temporal/resource conflicts, then measure non-keep repair generation separately from keep-world feasibility. A successful executable constraint evaluation is not yet an end-to-end repair or sandbox execution.
