# Medusa → OpenAccountants: tax-provider demo

**The pitch in one line:** Medusa is open-source commerce whose own docs say its tax engine "won't work for the US or varying rates within the same region." OpenAccountants is the **drop-in tax provider** that returns the destination-correct rate — state + local — signed off by a named licensed accountant.

```
Medusa cart (items + shipping address)
  └─ POST /store/carts/:id/taxes  →  OpenAccountants tax provider
        └─ OA MCP: load the verified US destination rates
              └─ Verdict:  ⚠️ under-charging — flat region rate misses local tax   ← the catch
                           ⚠️ over-charging — no sales tax in this state
                           ✅ correct destination rate
                 · Medusa flat rate vs OA rate, side by side
                 · the named CPA who signed off the rates
```

![Medusa → OpenAccountants demo](demo.svg)

> Regenerate the visual: `python make_svg.py` (static SVG, no deps) · animated GIF: `brew install vhs && vhs demo.tape`

## Why this one

This is a **real integration target, not just a demo**: Medusa ([`medusajs/medusa`](https://github.com/medusajs/medusa), ~34k★, MIT) has a clean tax-provider seam, and its [docs explicitly state](https://docs.medusajs.com/) the built-in calculation "will not work for the US or other countries with varying rates within the same region." OpenAccountants slots straight into that seam and fills the gap they've documented.

- **Medusa = the store, the cart, the checkout.**
- **OpenAccountants = the tax provider** — destination-correct state + local rates, no-tax states, and nexus awareness, with verified rules a real accountant signed off on.

## What it shows

Four carts priced by Medusa's flat region rate vs OpenAccountants:

| Ship to | Medusa flat | OpenAccountants | |
|---|---|---|---|
| **Chicago, IL** | 6.25% | **10.25%** | ⚠️ under-charging local tax |
| Portland, OR | 6.00% | **0.00%** | ⚠️ over-charging (no sales tax) |
| Austin, TX | 8.25% | 8.25% | ✅ correct |
| **Los Angeles, CA** | 7.25% | **9.50%** | ⚠️ under-charging local tax |

**The money shot:** the Chicago cart. The combined rate is **10.25%** (Illinois + Cook County + Chicago + RTA), but a single flat "US region" rate only carries 6.25% — so the store **under-collects local tax it's still liable to remit.** And Portland shows the opposite error: Oregon has no sales tax at all, so the flat rate **over-charges the customer.** Destination-correct rates fix both.

## Run it

```bash
git clone https://github.com/openaccountants/medusa-tax-demo
cd medusa-tax-demo
python pipeline.py                  # bundled sample carts (mock mode, no keys)
python pipeline.py samples/carts.json
```

### Go live

```bash
export OA_MCP_TOKEN=...     # OpenAccountants account token (uses the live verified rates)
python pipeline.py
```

To wire it into a real Medusa store, this becomes a Tax Module Provider whose
`getTaxLines` calls OpenAccountants — same logic as `tax_provider.py`.

## Files

| File | Role |
|------|------|
| `pipeline.py` | Orchestrator + CLI: carts → OA → verdict report |
| `medusa_client.py` | Normalizes Medusa carts |
| `oa_client.py` | OpenAccountants MCP JSON-RPC client (live or mock) |
| `tax_provider.py` | The destination rate lookup + Medusa-vs-OA contrast |
| `samples/carts.json` | Medusa-shaped carts |

## Honest notes

- `tax_provider.py` does **rate lookup + nexus signal**, not product taxability, exemptions, or marketplace-facilitator rules. Production leans on the full OA skill + an agent step; the named-CPA sign-off makes the rate relianceable.
- Rates (Chicago 10.25%, LA 9.5%, Austin 8.25%, OR 0%) are real combined figures; live, every value comes from `get_skill`. The verifier (Amir Pelinkovic) is the real OpenAccountants US lead.
