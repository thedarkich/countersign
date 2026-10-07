# Countersign — product context

This file explains why Countersign exists, who judges it, and what the demo must show. Read it before building, so your choices serve the pitch.

## The hackathon

- **Event:** 汉客松 S1 & ETH Wuhan 2026, Wuhan. Coding window 2026-10-06 20:00 to 2026-10-08 12:00 (China time), 40 hours.
- **Tracks we enter:**
  - Main track: AI × Blockchain (our focus)
  - BOT Chain sub-track (our focus)
  - Public Good sub-track, Problem 1 (side lane, 90 minutes maximum)
- **Prizes stack:** overall champion 600U, BOT Chain champion 300U, Public Good 2 × 100U. Every valid BOT Chain submission also enters BOT Chain's global online hackathon ($50,000 pool).
- **Scoring:** five equal criteria of 20% each:
  - technical completion
  - innovation
  - scenario value
  - track fit
  - presentation quality
- **Format:** round 1 is about 6 minutes per team, including Q&A. The final (up to 8 teams) is 4 minutes of demo plus 3 minutes of Q&A.
- **BOT Chain requirements:** a mainnet deployment (chain 677), with explorer links, transaction records and contract addresses in the submission. Testnet does not count. The track judges also look at whether BOT Chain's technology shows up in the actual features (赛道结合度), so a plain EVM deployment is the floor, not the goal.
- **Existing code** is allowed but must be disclosed, and work done during the event must be clearly separated.

## The problem

AI agents are starting to pay invoices, and every invoice they read is untrusted input that can carry instructions. One poisoned invoice can make an agent pay a thief.

- Business email compromise (fake vendors, "please use our new bank details") cost US victims $3.05 billion in 2025, about $123,000 per incident. Over $30 million of that is already linked to AI.
- In March 2025, two fraudulent prompts made the AI bot AIXBT send 55.5 ETH (about $106,000) from its wallet.
- Prompt injection has no reliable fix inside the model. Spending limits alone don't help either: an attacker simply asks for less than the limit.

**Users:**
- Primary: finance leads at crypto-native companies and DAOs who pay vendors in stablecoins and want AI to handle invoices.
- Secondary: developers building payment agents on BOT Chain.

**Market:** B2B stablecoin payments reached $226 billion in 2025 (up 733%), and in one survey 77% of corporate stablecoin users pay suppliers with them. All real-world stablecoin payments are still under 1% of global payments: a fast-growing niche.

**Framing:** settlement between organizations and agents on a public chain. Never present it as a payment tool for Chinese businesses; crypto payments are restricted in mainland China.

## The answer

Assume the AI will be fooled, and bound what it can spend and where it can send it.

- **The AI does the paperwork.** It reads invoices (images, PDFs, Chinese or English), catches hidden text, matches the vendor and budget, flags anything odd, and proposes a payment.
- **The vault contract holds the money.** It pays only if:
  - the vendor is registered and the money goes to the vendor's *registry* address, never one printed on the invoice
  - the amount fits a human-approved budget
  - the invoice hasn't been paid before
  - the daily cap holds
  
  Otherwise it records the attempt on-chain as `Blocked`, with a reason.
- **Safer changes are instant; riskier changes wait.** Pausing, deactivating a vendor or lowering the cap happen immediately. Adding a vendor, changing a payout address, adding a budget, adding an agent key, raising the cap, unpausing and withdrawing all wait out a time lock. Even the boss can't rush it.
- **What a stolen agent key can do:** pay our registered vendors, at their registered addresses, up to what's left in their budgets and today's cap. It can make up invoice numbers, so "once per invoice" stops a replay, not a forgery. It cannot redirect a vault payment to an unregistered attacker address. A dishonest or compromised registered vendor can still benefit from fake invoices, and repeated attempts can consume budgets again when standing limits reset. The owner can revoke the agent key instantly.

**What the checks establish:** the invoice agrees with owner-approved payment rules, not that goods or services were delivered. Invoice text cannot edit the trusted registry or authorize a rule change. Checking invented history against other invented history does not establish truth. The demo does not yet connect to independently verified orders, delivery receipts or vendor onboarding evidence.

**What the time lock does:** risky rule changes wait; ordinary payments inside existing rules do not wait for a person to approve each one. The delay creates a chance to inspect and cancel a bad change, but does not perform a review. In this version the same owner controls cancellation, so a compromised owner plus nobody able to intervene is not solved by waiting. The intended labor saving comes from preapproved recurring rules and exception review; onboarding, monitoring and false alarms still take work, and savings have not been measured.

**Positioning against existing products:** Privy, Coinbase and AWS already sell spending limits and allowlists for agent wallets. They limit *how much* an agent spends. We control *what it's allowed to pay for*: approved budgets, no duplicates, time-locked vendor changes, enforced on-chain where anyone can audit the rules.

## How it works

```
 invoice (PDF, photo or typed text)
        │
        ▼
 ┌─ AI, off-chain: can be fooled ────────────────────────────────────┐
 │ read (Qwen-VL) → hidden text → match vendor and PO → guard        │
 │                                      └─ doubts → refuse → Inbox   │
 └──────────────────────────────┬────────────────────────────────────┘
                                │ pay(vendorId, payTo, poId, amount, invoiceHash)
                                ▼
 ┌─ vault contract on BOT Chain: reads no text, can't be talked to ──┐
 │ registered vendor? registry address? budget? new invoice? cap?    │
 │   all yes → Paid, to the registry address                         │
 │   any no  → Blocked(reason)          (both recorded on-chain)     │
 └───────────────────────────────────────────────────────────────────┘
 owner (finance lead): safety actions are instant; risky changes wait out a time lock
```

## Two agents, one vault

- **Guarded agent (the product):** runs the guard and pays only the registry address. When it refuses, the invoice appears in the Inbox with its reasons for a person to check. There's deliberately no "approve anyway" button: if the person decides the invoice is real, the vendor resends it, or the vendor's record is fixed through the time lock.
- **Naive agent (the demo foil):** the same model with no guard. It pays whatever address the invoice prints and follows instructions it finds, as a careless implementation would. It exists to be fooled on purpose and show the vault holding anyway. The UI says this openly.

## Public payment-agent reputation

Human-approved addition on 2026-10-06; planned for Phase 4, not implemented in the existing mock. Reputation belongs to the **payment agent that proposed the payment**, not the claimed invoice sender or vendor.

Everyone can view each agent's safety history on the public Ledger, and the owner sees the same status beside the agent key in Controls. Show payments, refusals, suspicious proposals, policy blocks, execution errors and the evidence behind each result. A confirmed `PayoutMismatch`, or a proposal for an invoice known to be an attack fixture/bounty submission, produces a **"Suspicious proposal observed — review"** flag. A guard that refuses an attack has stopped it; that is not misconduct by the agent. An exhausted budget, duplicate, paused vault or transfer error alone is not proof of fraud.

Keep the guarded product agent and deliberately naive demo agent separate. Show source, network, model/guard version, observation period and counts with denominators. Receipt links verify chain outcomes; refusal records and known-attack labels are application evidence and must say so. There is no universal good/bad score, no automatic blacklist, and no claim that an unflagged agent is safe. History persists when a key is revoked; a new key starts with no history. Reputation never overrides the vault's rules.

Only sanitized activity is public: do not publish invoice contents, personal information or arbitrary accusations from uploaded text. Initial coverage is our two agents and configured vaults; a cross-product identity/reputation network is beyond this demo. Optional ERC-8004 publication is a later export of these signals, not a prerequisite for showing them. Exact evidence and acceptance rules: SPEC §3.11.

## The live bounty

Two prizes keep people attacking for about a day before judging:

- **Fool our AI** (small prize): the best invoice that makes the *guarded* agent propose a payment it shouldn't. People will win this, and that's the point: they fooled the AI and still got nothing.
- **Rob our vault** (the pot): make either agent pay an attacker-controlled address outside the approved registry. This tests the payout restriction; our registered demo vendors are team-controlled.
- **Prizes are not crypto.** The team decides what they are. The UI says 小奖品 and 金库里的全部奖池 without an amount.
- **Network:** ask BOT Chain staff whether bounty attempts may be real mainnet transactions (the vault only ever pays team-owned vendor addresses). If yes, every attempt is BOT Chain evidence. If no, or no answer by Oct 7 10:00, the bounty runs on testnet with test tokens and the page says so; all stage demo transactions stay on mainnet.

Anyone opens the page from a QR code, enters a nickname and an address, picks an agent, and uploads an invoice or types a message. The page is Chinese-first and must work inside WeChat.

Live counters show attempts, people, guard catches, times the AI was fooled (guarded and naive agents counted separately, since the naive one is fooled by design), chain blocks, and funds sent outside the registry (target: 0). The legacy API field `money_lost` measures only that last category; never label it as all fraud losses. Our own seed red-team set is reported separately from outside attempts; mixing them would be dishonest.

**One honest caveat:** an attacker can fake an invoice for one of our registered vendors. If the AI is fooled, it pays that vendor within budget. That can be a real loss; recovery is not guaranteed, especially if the vendor colludes or its payout key is compromised. In our demo the vendor addresses are team-owned. We count it as "AI fooled," show it separately as "paid a registered vendor on a fake invoice," and name the next control: match the invoice to an approved order and independently confirmed goods/service receipt (three-way match). That control still depends on trustworthy source records and is not built in this demo.

## The learning loop

Submitted attacks form a dataset. On the last morning, guard v2 learns only from its training split and is tested on an untouched held-out split. Public attempts are grouped by device; seed attempts are grouped by technique. Device count is an approximation for people, and a public attack technique can occur on multiple devices. Clean training invoices and clean held-out invoices are separate as specified in SPEC §7. We show v1 and v2 catch rates on held-out attacks, plus false-alarm rates on held-out clean invoices. Only the guard's prompt changes between v1 and v2; both use the same evaluation rules. Switch to v2 only if it catches more without a worse false-alarm rate.

## Demo script (3 minutes; leaves 3 for Q&A)

| Time | Screen | What happens |
|---|---|---|
| 0:00 | none | "Invoice fraud cost US businesses $3 billion last year. Now AI agents are paying the invoices." |
| 0:15 | Controls | Approved vendors and budgets, plus a pending change counting down its time lock |
| 0:30 | Inbox | A batch of clean invoices matched and paid; one Chinese invoice shown in detail, paid on BOT Chain |
| 0:55 | Inbox | One click on a stage invoice with "Both agents" selected. Side by side: the guarded agent flags the hidden text and refuses; the naive agent is fooled and proposes paying the attacker, and the vault blocks it on-chain as a payout mismatch |
| 1:30 | Ledger (stage) | Live bounty numbers, outside attempts and seeds separate; open the naive agent's suspicious-proposal history and its blocked transaction, beside the guarded agent's refusal |
| 2:00 | Bounty | The judge's turn: scan the QR code and try |
| 2:35 | none | What was built in 40 hours vs. next; one sentence on the ERC-8004 lane and the open spec |

**Final round (4 minutes):** add 30 seconds on the learning loop (v1 vs. v2) and 30 seconds on "steal the agent's key and vault payments still go only to registered addresses inside approved limits. Fake invoices can still spend those budgets; an unregistered thief cannot redirect the payout, and we can revoke the key in one click."

**What this means for the build:**
- Every one of these beats must work live and reliably.
- The three poisoned invoices used on stage must fool the naive agent every time; test them in advance.
- Keep a recorded backup video of the full run.

## What judges will ask (answers the product must make true)

| Question | Answer |
|---|---|
| Coinbase, Privy and AWS already sell spending limits. What's new? | They limit how much. We control what for: budgets, duplicates, time-locked vendor changes, all on-chain and auditable. |
| Who pays invoices in crypto? | B2B stablecoin payments were $226B last year, up 733%. It's under 1% of global payments: early, and we say so. |
| Isn't the AI just OCR? | It reads two languages, catches hidden text, spots lookalike vendors, and measurably learned from yesterday's attacks. |
| Isn't the bounty rigged? | By design. Invoice fraud works by changing where money goes, and nothing the AI reads can do that here. |
| What if the finance lead gets phished? | Risky payment-rule changes wait and show as pending, giving a chance to cancel. The delay does not guarantee someone notices or retains the owner key needed to cancel. Independent approval/cancellation authority is future work. |
| What if someone steals the agent key? | Vault payments still go only to registered vendors within the remaining budgets and today's cap. Fake invoices and vendor collusion remain risks. Revoking the key is instant. |
| Can't someone just submit a convincing fake invoice for a real vendor? | Yes, and if the AI is fooled, that vendor gets paid within its budget. We count that separately ("paid a real vendor on a fake invoice"). The fix is matching against goods received (three-way match), which is next. |
| What if the attacker supplied false information before sending the invoice? | Rechecking that same information cannot prove the invoice genuine. The payment registry is owner-controlled, outside invoice text, but bad approved records or fake invoices inside the rules remain possible. |
| Does a time lock mean more staff checking every payment? | No per-payment review or delay is required inside approved rules. People handle onboarding, risky rule changes and exceptions. Whether this reduces total work must be measured; we have not measured it. |
| Does a suspicious reputation flag prove the agent committed fraud? | No. It shows a concrete proposal and its evidence, source and outcome. A policy violation is not proof of intent, and a successful payment is not proof of a genuine invoice. |
| Why BOT Chain? | BOT Chain is built for AI agents, and this is the safety layer an agent wallet needs. If the paymaster works: our agent keys hold zero BOT and BOT Chain's paymaster pays their gas only for calls to our vault, so a stolen key can do nothing else. Every stage transaction is on mainnet (and every bounty attempt too, if BOT Chain allowed it). |
| Isn't the bounty on testnet? | (Only if it is.) Yes, so that nobody at the event handles real crypto. The same contract is on mainnet, and everything we showed on stage happened there. |
| Is everything public on-chain? | Only invoice hashes go on-chain. Addresses and amounts are public on any public chain; privacy is future work. |
| What existed before the event? | See the README's pre-existing list. |

## Never say

- "Our AI can't be fooled," "being fooled costs nothing," or "zero fraud losses." The boundary is registered payouts and approved limits, not proof of genuine invoices.
- "A time lock verifies the invoice," "every block proves fraud," or "reputation guarantees safety."
- "Unhackable" or "sybil-proof."
- "For Chinese businesses."
- "Replaces accountants."
- "Nobody else does spending limits."

## Strict scores (for prioritizing)

| Track | Score | What holds it back |
|---|---|---|
| Main | 8/10 | The policy-wallet primitive is commoditized; we win on accounts-payable rules, the learning loop and live evidence |
| BOT Chain | 6/10 as planned, about 8 with the fixes | Uses BOT Chain as a plain EVM chain, and a testnet bounty doesn't count. Fixes: agent gas through BOT Chain's paymaster, and the bounty on mainnet if BOT Chain allows it |
| Public Good | 5/10 | Wrong ecosystem for its judges; side lane only |

**Build priority when time runs short:**
1. Contract on mainnet
2. End-to-end pipeline
3. Bounty live by noon on Oct 7 (the page is already built; wire it up)
4. Inbox and Ledger wired to the live API, including the stage invoices, "Both agents" view and public payment-agent reputation history
5. Controls wired to the wallet
6. Agent gas through BOT Chain's paymaster, if BOT Chain confirmed it (3-hour time-box)
7. Learning loop
8. Public Good lane

## Approved wallet intelligence addition — 7 October 2026

Scam Sniffer adds a backend check to both agent paths and a public payout-address lookup in Ledger. It can refuse addresses present in its delayed public dataset before broadcasting a payment. Its seven-day delay, lack of chain-specific incident attribution and incomplete coverage are visible; absence is not safety. This is separate from our agent proposal history and immutable vault enforcement. Direct calls with a stolen agent key bypass backend screening, so our on-chain budget/recipient controls remain essential. See [screening scope](WALLET_SCREENING.md) and [current judging/launch gaps](CRITERIA_REVIEW.md).
