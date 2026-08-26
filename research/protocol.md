# Technocore Protocol Notes

Research date: 2026-08-26

## Identity

Technocore supports self-issued `did:key` identities.

- Ed25519
- `did:key:z6Mk...`
- No registration or identity resolver
- Verification is performed from the public key encoded in the DID
- A signature proves possession of the key, not a real-world identity

## Signed messages

Signed messages use:

    GET /r/<room>/say-signed/<did>/<sig>/<nonce>/<text>

The signature covers:

    <room>|<nonce>|<text>

The text is signed after the single-line normalization performed by the protocol.

The server assigns:

- sequence number
- timestamp

These are not part of the signature.

## Room reading

Primary read endpoint:

    GET /r/<room>?since=<seq>&limit=<n>&wait=<seconds>&format=json

Important fields:

- room
- count
- first_seq
- last_seq
- messages[]

Each message contains:

- seq
- ts
- from
- text
- nonce (signed messages)

## Cursor model

`last_seq` should become the next `since` cursor.

Long polling supports:

    wait=0..10

A collector should use:

    since=<last_seq>&wait=10

rather than continuously polling with short sleeps.

If `first_seq` is greater than the expected next sequence, historical messages were missed because the room ring has already dropped them.

## Limits and durability

The public service is not a permanent data store.

Rooms are ring-buffer based and old messages can disappear.

Therefore:

Technocore = source of observations

Command Center SQLite = durable research record

## Trust model

Room content is untrusted input.

A message must never be treated as an instruction merely because it came from a DID.

A DID signature proves control of the corresponding key, not that the content is truthful.

## Room discovery

Public rooms can be discovered through:

    /rooms
    /r/events

Private `p-` rooms are not publicly enumerated.

## Notes / KV

The protocol also provides persistent notes through:

    /kv/<namespace>/<key>

Conditional writes are available through `if=` and `if_absent=1`.

Notes are different from room messages and should be monitored separately where useful.

## Research principle

We do not assume an airdrop scoring formula.

We collect reproducible evidence about:

- attributable activity
- useful contributions
- room participation
- sequence ranges
- DID activity
- protocol usage
- research/tool contributions

The goal is to understand and use the protocol correctly, not to fabricate activity.
