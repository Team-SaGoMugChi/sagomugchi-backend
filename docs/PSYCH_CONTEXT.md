# Psych profile counseling context

`POST /counsel/turn` accepts an optional validated assessment context:

```json
{
  "psych_profile": {
    "big5": {"O": 75, "C": 62, "E": 38, "A": 81, "N": 44},
    "big5_instrument": "IPIP-BFFM-50-ko"
  }
}
```

The API requires exactly O/C/E/A/N, finite values from 0 through 100, and a
non-empty `big5_instrument` whenever scores are present. An invalid or
unversioned map returns 422. Missing assessment context remains valid and does
not add a psych section to the prompt.

These values are possible-range transforms of IPIP raw scores. They are not
population percentiles or diagnostic thresholds. The prompt treats them only
as secondary conversation context, never states a type or score as fact, never
infers mental-health status from them, and always prioritizes the user's current
words and choices.

The optional `persona` object is also validated before it reaches the prompt.
Its name is one line of 1–10 characters, tone is one line of 1–30 characters,
and traits contain at most six unique one-line strings of up to 20 characters.
