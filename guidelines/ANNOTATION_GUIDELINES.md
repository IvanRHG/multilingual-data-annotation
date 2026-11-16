# Annotation Guidelines (v1.0)

These guidelines define how each text in `data/annotations.jsonl` is labeled. They are written so that two annotators who follow them independently should reach the same labels on clear cases, and record their reasoning on unclear ones.

Rule numbers (for example **4.3**) are referenced in the `notes` field of the dataset.

---

## 1. General workflow

1. Read the whole text once before labeling anything.
2. Label in this order: **language → content type → sentiment → intent → topic**. Later labels often depend on earlier ones.
3. Label what the writer **means**, not only the literal words (see sarcasm, **3.4**).
4. Use only information in the text. Do not guess the writer's situation beyond what is written.
5. If a label is still uncertain after applying the rules, choose the best option, set `ambiguous: true`, and explain the alternatives in `notes`.
6. `notes` is **required** when `ambiguous` is `true` or `language` is `mixed`. Notes are also useful when a non-obvious rule decided the label.

---

## 2. Language

| Label | Definition |
|---|---|
| `es` | Spanish |
| `en` | English |
| `fr` | French |
| `mixed` | Two or more languages, each contributing at least one full phrase or clause |

**2.1** Label the language of the text, not the country of the writer.

**2.2** A single borrowed word that is common in the main language does **not** make a text mixed. *“Je suis trop happy avec ma commande”* → `fr`. Use `mixed` only when the writer switches language across phrases or clauses: *“El delivery llegó late otra vez, so annoying.”* → `mixed`.

**2.3** For `mixed`, list the languages in `notes` (for example “Spanish + English”).

---

## 3. Sentiment

| Label | Definition | Positive example | Negative example (not this label) |
|---|---|---|---|
| `positive` | The writer expresses satisfaction or a favorable evaluation | “Livraison rapide, produit conforme.” | “The product is okay.” (lukewarm → `neutral`) |
| `negative` | The writer expresses dissatisfaction, or reports something that does not work | “La app se cierra sola…” | “¿Cómo cambio el correo…?” (plain question → `neutral`) |
| `neutral` | No clear evaluation: questions, requests, plain facts, lukewarm remarks | “Is there a student discount?” | “Love the new dark mode!” (→ `positive`) |
| `mixed` | Clearly positive **and** clearly negative content in the same text | “The headphones sound great, but the ear cushion started peeling.” | “Le produit est correct, sans plus.” (→ `neutral`) |

**3.1** A problem report counts as `negative` even if the tone is calm, because it describes something that failed.

**3.2** A thank-you attached to a neutral fact (“Received the replacement today, thank you.”) is `positive`.

**3.3** Lukewarm evaluations (“okay”, “correct, sans plus”) are `neutral`. Use `mixed` only when both sides are clearly present.

**3.4 Sarcasm.** Label the intended meaning. Signals: quotation marks around praise words, “Oh great…”, “bravo…” after a described failure. *“Qué servicio tan ‘eficiente’.”* → `negative`.

---

## 4. Intent

What the writer wants to achieve with the message.

| Label | Definition | Example |
|---|---|---|
| `complaint` | Expresses dissatisfaction or reports a problem, **without** asking for a specific action | “Le colis devait arriver mardi… toujours rien.” |
| `praise` | Expresses satisfaction with the product or service | “Excelente atención de Laura en el chat.” |
| `opinion` | Evaluates something without a dominant complaint or praise | “The product is okay.” |
| `question` | Asks for information | “Can I change the delivery address after the order has shipped?” |
| `request` | Asks the company to do something concrete | “Please delete my account.” |
| `suggestion` | Proposes an improvement | “Il faudrait ajouter plus de tailles pour les enfants.” |
| `information` | Shares a fact or update, with no request or evaluation as main purpose | “Merci, j'ai bien reçu le remboursement.” |

**4.1** A problem description with no explicit action is a `complaint`, even if the writer clearly hopes for help.

**4.2** If a text complains **and** asks for a concrete action (refund, exchange, cancellation), label `request`. The action is what the company must respond to.

**4.3 Contrast.** In “X, but Y” / “X, pero Y” / “X, mais Y”, the clause after the connector usually carries the main point. *“Buen producto, pero el envío tardó el doble.”* → intent `complaint`, sentiment `mixed`.

**4.4 Question vs. request.** “Can I…?” / “¿Se puede…?” asks whether something is possible → `question`. “Can you send me…?” / “Pouvez-vous m'envoyer…?” asks the company to act → `request`.

**Consistency checks** (enforced by the validator): `praise` requires `positive` sentiment; `complaint` requires `negative` or `mixed`; `opinion` requires `neutral` or `mixed`.

---

## 5. Topic

| Label | Covers |
|---|---|
| `billing` | Payments, charges, refunds, invoices, subscriptions, payment methods, discounts |
| `delivery` | Shipping, delays, tracking, packaging, transport damage, delivery locations |
| `product_quality` | Product characteristics: quality, size, fit, durability, features, **value for the price** |
| `account_access` | Login, passwords, profile settings, account deletion |
| `customer_service` | Interactions with support agents, response times |
| `app_experience` | Usability, crashes, and features of the app or website |
| `other` | Not related to the service, or about the service in general with no specific aspect |

**5.1** When cause and symptom point to different topics, label the **symptom** the writer experiences. *“Je n'arrive pas à me connecter depuis la mise à jour.”* → `account_access`.

**5.2** If several topics appear, choose the one connected to the intent (what the writer wants addressed).

**5.3** If two topics have equal weight and neither is linked to the intent, choose the first one mentioned.

**5.4** Comments on whether a product is worth its price are `product_quality`. Questions about payments are `billing`.

---

## 6. Content type

| Label | Definition |
|---|---|
| `product_review` | Evaluation of a purchased product or the purchase experience, written for other customers |
| `support_message` | Message addressed to the company's support team |
| `survey_comment` | Answer to a satisfaction survey or feedback form |
| `social_post` | Public post or comment on social media |

When the type cannot be decided from wording alone, choose the most likely type and add a note.

---

## 7. Quality checklist before submitting

- [ ] Every label belongs to the allowed set in `schema/label_schema.json`.
- [ ] Intent and sentiment pass the consistency checks in section 4.
- [ ] `notes` is filled for every `ambiguous` or `mixed` item.
- [ ] No text contains real personal data (names of real people, emails, phone numbers, addresses).
- [ ] `python scripts/validate_annotations.py` finishes with 0 errors.
