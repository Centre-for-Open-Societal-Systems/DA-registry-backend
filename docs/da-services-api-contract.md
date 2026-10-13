# DA Services ↔ DA Registry: API contract

For the DA Services (Frappe) team. How DA Services sends a Development Agent to
the DA Registry (OpenG2P) and reads it back.

DA Services talks to the registry in two ways:

- **Partner API** (this document), server to server, signed by DA Services:
  - **Bulk import:** push each DA from the Admin's Excel file. The registry
    validates it, checks the Fayda ID is unique, approves it automatically
    and gives it a DA-ID.
  - **Status of a push**, and **DCI search** to look DAs up by DA-ID, Fayda ID
    or name.
- **Staff API**, with the signed-in user's Keycloak token: the single DA form,
  approving or rejecting a new DA, search and view, and a DA editing their
  profile (change request). Roles and Woreda scope are checked by the
  registry, and approvals happen in the registry. See
  [da-services-staff-api.md](da-services-staff-api.md).

The browser never calls the registry directly; the Frappe backend makes
these calls.

| | Local stack | Deployment |
|---|---|---|
| Partner API | `http://localhost:8106` | TODO(devops) |
| Signature / consent checks | off | on (see [Security](#security)) |

---

## 1. Push an approved DA

```
POST /partner/ingest_data?data_model=DA_SERVICES&register_id=6f1c2d8e-4a7b-4c3e-9d2f-8b5a1e7c3f90&intake_form_id=6f1c2d8e-4a7b-4c3e-9d2f-8b5a1e7c3f91
Content-Type: application/json
```

### Request body

```json
{
  "header": {
    "version": "1.0.0",
    "message_id": "9f0c2e5a1b7d4c3e8a6f2b1c0d9e8f7a",
    "message_ts": "2026-10-06T09:15:00Z",
    "sender_id": "da-services",
    "data_model": "DA_SERVICES"
  },
  "signature": "<signature of header + message>",
  "message": {
    "reference_id": "FR-DA-0001",
    "source": "WEB_INTAKE",
    "approved_by": "Dr. Tewodros M. (Woreda Supervisor, Tahtay Adiyabo)",
    "da": {
      "salutation": "Dr",
      "first_name": "Frehiwot",
      "father_name": "Assefa",
      "grandfather_name": "Bekele",
      "fayda_id": "804512345601",
      "gender": "Female",
      "marital_status": "Married",
      "birth_month_ec": 6,
      "birth_year_ec": 1986,
      "phone_number": "0911556677",
      "telegram_number": "0911556677",
      "alternate_number": null,
      "email": "frehiwot.assefa@example.org",
      "education_level": "Masters",
      "specialisation": "Agronomy",
      "position": "Senior DA",
      "joining_date": "2017-09-11",
      "kebele_id": "kebele-ET010101101001"
    }
  }
}
```

`header.message_id` must be unique per request. `sender_id` and `signature`
must be present (non-empty).

### `message`

| Field | Required | Meaning |
|---|---|---|
| `reference_id` | Yes | The DA's record id in DA Services. Stored in the registry (`upstream_reference`) for tracing |
| `source` | No (default `WEB_INTAKE`) | `WEB_INTAKE` (entered on a form) or `CSV_IMPORT` (from a bulk file). With `WEB_INTAKE` every required field below must be filled |
| `approved_by` | Recommended | Who approved it in DA Services. Recorded as the registry approver |
| `da` | Yes | The DA, below |

### `message.da`

Codes may be sent as codes or labels (e.g. `SENIOR_DA` or `Senior DA`); case
does not matter.

| Field | Required | Format / values |
|---|---|---|
| `salutation` | No | `MR`, `MRS`, `DR` (Mr, Mrs, Dr) |
| `first_name` | **Yes** | Name. Letters (Latin or Ethiopic), spaces, `-`, `'`; max 100 |
| `father_name` | **Yes** | Father's name. Same format |
| `grandfather_name` | No | Grandfather's name. Same format |
| `fayda_id` | **Yes** | Fayda FIN, 12 digits (spaces / dashes are removed). One DA per Fayda ID (also enforced by a unique index on active registered DAs) |
| `gender` | Yes* | `MALE`, `FEMALE` |
| `marital_status` | Yes* | `SINGLE`, `MARRIED`, `DIVORCED`, `WIDOWED` |
| `birth_month_ec` | Yes* | 1–13 (Ethiopian calendar) |
| `birth_year_ec` | Yes* | 4-digit EC year; the DA must be 18 or older |
| `phone_number` | Yes* | Ethiopian number: `0911234567` or `+251911234567` (a 9-digit number gets its leading 0 back) |
| `telegram_number` | No | Phone number, same format |
| `alternate_number` | No | Phone number, same format |
| `email` | Yes* | Valid email; stored lower case |
| `education_level` | Yes* | `CERTIFICATE`, `DIPLOMA`, `DEGREE`, `MASTERS` |
| `specialisation` | Yes* | `CROP_PRODUCTION`, `LIVESTOCK`, `NATURAL_RESOURCES`, `AGRONOMY`, `HORTICULTURE`, `OTHER` |
| `position` | Yes* | `DEVELOPMENT_AGENT`, `SENIOR_DA` |
| `joining_date` | No | `YYYY-MM-DD` (or `DD/MM/YYYY`); not in the future |
| `kebele_id` | **Yes**, or the four names | Master Data kebele id, e.g. `kebele-ET010101101001` (preferred: names repeat across woredas) |
| `region`, `zone`, `woreda`, `kebele` | Instead of `kebele_id` | Names as in Master Data; resolved region → kebele |

\* Required when `source` is `WEB_INTAKE`. For `CSV_IMPORT` a blank value is
accepted; a filled value must still be valid.

### Response

The registry answers as soon as it has accepted the request. Processing
(validation, duplicate check, approval, DA-ID) happens in the background,
usually within a minute or two.

```json
{
  "response_header": {"response_status": "SUCCESS", "response_error_code": "", "response_timestamp": "2026-10-06T03:16:28.698394"},
  "response_body": {"response_payload": {"correlation_id": "aaac69f6d383456bbd43cd682e85cd31"}}
}
```

Keep `correlation_id` with the DA in DA Services.

### What happens next

| Case | Registry outcome | How DA Services finds out |
|---|---|---|
| Valid, Fayda ID not yet used | Approved → register → DA-ID (`DA-` + 10 digits) | Status `GENERATED` with `da_id` (§3) |
| Fayda ID already registered, or in another pending submission | Stopped with the reason ("Fayda ID … is already registered as DA-…") | Status `EXCEPTION`, `DUPLICATE_IDENTITY` (§3) |
| Invalid (format, missing required field, unknown kebele) | Stopped with a reason | Status `EXCEPTION` with the reason (§3) |

So **check duplicates before you push** (§2: search by Fayda ID, and look
inside the file for repeats when importing). The registry check is the last
guard, not the place to discover duplicates.

---

## 2. Read DAs (DCI search)

```
POST /dci/registry/sync/search
Content-Type: application/json
```

```json
{
  "signature": "<signature>",
  "header": {"version": "1.0.0", "message_id": "…", "message_ts": "…", "action": "search",
             "sender_id": "da-services", "receiver_id": "da-registry"},
  "message": {
    "transaction_id": "…",
    "search_request": [{
      "reference_id": "q1", "timestamp": "…", "locale": "eng",
      "search_criteria": {
        "version": "1.0.0", "reg_type": "DA", "reg_record_type": "DA",
        "query_type": "expression",
        "query": {"type": "expression",
                  "value": {"expression": {"query": {"search_text": {"$eq": "804512345601"}}}}}
      }
    }]
  }
}
```

`search_text` matches DA-ID, Fayda ID, names, phone, email and location
(partial match). Each result is under `reg_records[].da_details`:

```json
{
  "da_id": "DA-6453519520", "internal_record_id": "…", "fayda_id": "804512345601",
  "name": {"salutation": "DR", "given_name": "Frehiwot", "father_name": "Assefa",
           "grandfather_name": "Bekele", "full_name": "Frehiwot Assefa Bekele"},
  "sex": "female", "marital_status": "MARRIED", "birth_month_ec": 6, "birth_year_ec": 1986,
  "contact": {"phone_number": "0911556677", "telegram_number": "0911556677",
              "alternate_number": "", "email": "frehiwot.assefa@example.org"},
  "education_level": "MASTERS", "specialisation": "AGRONOMY", "position": "SENIOR_DA",
  "joined_date": "2017-09-11", "source": "WEB_INTAKE",
  "posting": {"region": "Tigray", "zone": "North Western", "woreda": "Tahtay Adiyabo",
              "kebele": "Adi Hageray", "geo_lowest_level_value_id": "kebele-ET010101101001"},
  "record_status": "ACTIVE", "registration_date": "…", "last_updated": "…"
}
```

`search_text` is a partial match, so check that a returned record's
`fayda_id` equals the Fayda ID you searched for before treating it as a
duplicate.

### Filter by location or position

Expression queries also take exact filters on these DA fields (several fields
are combined with AND): `region_name`, `zone_name`, `woreda_name`,
`kebele_name`, `geo_lowest_level_value_id`, `position`,
`specialisation`, `upstream_reference`. Operators: `$eq`, `$ne`, `$in`, `$nin`
(and `$gt`/`$lt`/… on numbers and dates). Use this, not `search_text`, to
scope a Supervisor to their Woreda:

```json
"query": {"type": "expression", "value": {"expression": {"query": {
  "woreda_name": {"$eq": "Tahtay Adiyabo"},
  "position": {"$eq": "SENIOR_DA"}
}}}}
```

`geo_lowest_level_value_id` with `$in` lists the DAs of several Kebeles.
Results are paged, 10 by default; add `"pagination": {"page_size": 50,
"page_number": 1}` to `search_criteria`. Each response carries
`pagination.total_count`.

---

## 3. Status of a push

```
GET /partner/da/status?correlation_id=<from the push response>
GET /partner/da/status?reference_id=<your record id>
```

One of the two. With `reference_id` the latest push of that record is
returned. Answers 404 when nothing is found, 400 when neither is given.

```json
{
  "correlation_id": "24507f2839fe49c8946a6d80b94c4ea7",
  "reference_id": "FR-DA-0001",
  "state": "GENERATED",
  "reason": null,
  "exception_type": null,
  "da_id": "DA-3803532319",
  "record_status": "ACTIVE",
  "application_reference": "2026OCT07-25529-1027",
  "received_at": "2026-10-07T07:04:55.793904",
  "updated_at": "2026-10-07T07:05:29.894349"
}
```

| `state` | Meaning | What DA Services does |
|---|---|---|
| `QUEUED` | Received, still being processed | Ask again in 10–30 s |
| `GENERATED` | Registered; `da_id` is set | Save the DA-ID on the DA |
| `EXCEPTION` | Stopped; `reason` says why | Show it to the Admin; send a corrected record |
| `FAILED_RETRY` | An attempt failed and the registry is retrying | Ask again later |

`exception_type` groups the reason for the exceptions panel:
`DUPLICATE_IDENTITY`, `INVALID_KEBELE`, `MISSING_MANDATORY_FIELD`,
`INVALID_FIELD`, `REJECTED`.

The registry retries every failed step a few times, a validation error
included, so a bad record shows `FAILED_RETRY` (already with its reason) for a
few minutes before it settles as `EXCEPTION`. A valid record usually reaches
`GENERATED` within one to two minutes.

---

## Security

In deployments the push and the search are checked:

- **Signature:** DA Services must be registered as a partner in Partner
  Management with its signing key, and sign `header` + `message`.
- **Consent (DCI search):** searches need a consent object, or DA Services must
  be allow-listed for searches across subjects.

Both are off in the local stack. TODO(devops): register DA Services as a
partner and agree the consent set-up per environment. The status lookup (§3)
returns no personal data beyond the DA-ID; in deployments it should still only
be reachable by DA Services (network policy or gateway).

## Open items

1. **Updates** (a DA edits their profile): these go through the registry staff
   API as change requests, with the DA's Keycloak token, not through this
   partner API. See [da-services-staff-api.md](da-services-staff-api.md).
2. **Bulk import:** push one request per DA and pace them (e.g. 1,000–2,000 at a time).
   Throughput still to be load-tested.
3. Field names above are the registry's proposal; change requests welcome
   before DA Services builds against them.
