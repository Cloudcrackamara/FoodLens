# **PRODUCT INTEGRITY & AUTHENTICATION PLATFORM**

## 

## **Product Integrity as a Service**

## **A Digital Trust Infrastructure for Product Authenticity, Traceability and Brand Protection in Africa**

A manufacturer-led platform that assigns unique digital identities to product units, packs, and batches, verifies those identities through a public consumer interface, connects product events to retailer transactions, and detects suspicious identity reuse across distribution and retail channels.

**Document Type:** Strategic Product Concept & Business Innovation Proposal  
**Initial Market:** Nigeria, with an Africa-first expansion strategy  
**Primary Customers:** Manufacturers, brand owners and authorized distributors  
**Product Category:** Digital Product Authentication, Traceability and Anti-Counterfeit Intelligence  
**Development Stage:** Concept validation and demonstration prototype

---

## **1\. Executive Summary**

Counterfeit, adulterated and misrepresented products represent a significant challenge to consumer safety, public health, brand reputation, commercial integrity and economic development across Africa.

Manufacturers invest heavily in producing legitimate goods, developing trusted brands and maintaining quality standards. However, counterfeiters can exploit weaknesses in product identification and distribution systems by copying packaging, reproducing product labels, reusing legitimate registration numbers and introducing inferior or dangerous products into the market.

Traditional product registration systems establish important information about a registered product or manufacturer. However, a registration number shared across thousands of units does not, by itself, establish the authenticity of an individual item in a consumer's possession.

The proposed **Product Integrity & Authentication Platform** addresses this gap by establishing a digital identity for every product unit, pack and batch, linking those identities to trusted manufacturer records, recording authorized supply-chain and retail events, and detecting suspicious identity reuse through transaction-aware risk intelligence.

The platform will provide four interconnected capabilities:

1. **Unit-level digital identity:** Every registered product unit receives a unique, unpredictable identifier linked to its manufacturer, product details, batch and packaging hierarchy.  
2. **Accessible product verification:** Consumers can scan a QR code to retrieve product identity information and its recorded status without necessarily installing an application.  
3. **Transaction-linked lifecycle tracking:** Retail POS systems and a lightweight mobile merchant interface can record product receipt, sale, return and other authorized events.  
4. **Counterfeit-risk intelligence:** The platform analyzes duplicate scans, conflicting locations, suspicious scan patterns and inconsistent lifecycle events to identify possible counterfeiting and product identity abuse.

The proposed solution is not merely a QR-code generator or a product registration directory. It is a manufacturer-led digital trust infrastructure designed to connect product identity, commercial transactions, consumer verification and actionable risk intelligence.

Its long-term value lies in helping manufacturers move from reactive counterfeit investigations toward earlier detection, evidence-based investigations and more transparent product distribution.

**Core proposition:** Every product should have a verifiable digital identity, every authorized lifecycle event should be accountable, and suspicious activity should produce actionable intelligence.

## **2\. The Problem We Are Solving**

### **2.1 Registration does not equal individual-item authentication**

Regulatory registration systems play an essential role in establishing the legitimacy of products approved for sale. However, a product registration number generally identifies a product registration, not each individual unit manufactured under it.

A counterfeiter may reproduce the registration number, product description, label and packaging of a legitimate product. Consequently, checking the registration number alone may not distinguish a genuine unit from a counterfeit carrying copied information.

The missing capability is reliable, unit-level identity and evidence of how that identity has moved through the commercial lifecycle.

The proposed platform is designed to complement relevant regulatory systems, not replace their authority or product-approval functions.

### **2.2 Product identity can be copied and reused**

Counterfeiters can photograph or reproduce a legitimate product's QR code and place it on counterfeit packaging.

If the verification system simply checks whether the QR code exists in a database, a copied code may initially return a legitimate result.

A reliable solution must therefore consider more than whether an identifier exists. It must evaluate the identifier's recorded lifecycle, transaction status and observed scan patterns.

### **2.3 Limited visibility after manufacturing**

Manufacturers may not have a consolidated, unit-level view of what happens to their products after they leave the factory.

Products pass through distributors, wholesalers, retailers and informal sales channels. Information about receipt, movement, sale and suspicious activity may be fragmented across disconnected systems or absent altogether.

This makes it harder to investigate where counterfeit products entered the market, identify affected batches and assess the scale of a suspected incident.

### **2.4 Unequal access to authentication technology**

Large retailers may operate sophisticated POS and inventory systems, while smaller shops and informal retailers may rely on manual processes or basic smartphones.

A solution that requires expensive infrastructure at every retail location would exclude a substantial part of the distribution ecosystem.

The proposed platform therefore supports both integration with existing POS systems and a lightweight mobile merchant interface.

### **2.5 Limited actionable intelligence**

A basic QR verification system may return a result without helping a manufacturer understand the broader pattern of misuse.

For example, repeated scans of the same product identity from distant locations, especially after a recorded sale, could indicate that a legitimate code has been copied and reproduced.

The opportunity is to convert individual verification events into intelligence that helps manufacturers prioritize investigations and take appropriate action.

## **3\. The Proposed Solution**

The Product Integrity & Authentication Platform is a cloud-based, manufacturer-led system that establishes digital identities for individual products and records relevant lifecycle events.

It combines a secure product identity registry, consumer-facing verification, merchant transaction capture, and a counterfeit-risk detection engine.

### **3.1 Unique unit-level product identity**

Each participating manufacturer registers its products and creates production batches within the platform.

The system generates a unique, unpredictable public identifier for each individual product unit. The identifier is encoded into a QR code and linked to the product's digital record.

The record may include:

* Manufacturer and brand.  
* Product name, type, size and relevant product attributes.  
* Batch or lot number and manufacturing information.  
* Expiry date, where applicable.  
* Parent pack or carton identity.  
* Current recorded lifecycle status.  
* Relevant manufacturer-approved product information.

The platform should use cryptographically secure random identifiers, database uniqueness constraints and protected internal records. Public identifiers must not be predictable derivatives of internal database IDs.

Product units, packs, cartons and batches will have linked identities so that the platform can represent relationships between individual items and their larger packaging or production groups.

This creates a foundation for unit-level verification and traceability.

### **3.2 Consumer product verification**

Consumers access a mobile-friendly verification page by scanning the QR code with their smartphone camera.

The platform checks the identifier against its registered records and returns a clear result.

Possible outcomes include:

* **Identity recognized:** The identifier belongs to a record issued by an authorized participating manufacturer.  
* **No prior sale recorded:** The unit has no confirmed retail sale event in the platform's records.  
* **Previously sold:** A confirmed sale has already been recorded for that identity.  
* **Suspicious activity detected:** The identifier has conflicting or anomalous scan or lifecycle events.  
* **Invalid identity:** The identifier was not issued by the platform or fails the relevant validation checks.  
* **Batch or product warning:** The manufacturer has recorded a relevant recall, expiry or other product notice.

The interface should explain what each result means and avoid presenting an identity match as conclusive proof of physical authenticity.

Consumers may also report suspected counterfeit products, creating an additional source of evidence for manufacturers and authorized investigators.

### **3.3 Transaction-linked product status**

The platform connects product identity to retail checkout and inventory processes.

Where an existing POS system supports integration, the platform receives an authorized transaction event through a secure API or connector.

Where a retailer lacks a suitable POS system, the merchant can use a mobile web application to scan products, record receipts and confirm sales.

When a legitimate checkout is completed, the relevant product unit's lifecycle record is updated to reflect the confirmed sale.

Subsequent scans can then be evaluated against that transaction history.

Importantly, a consumer scan does not change the item's official sale status. Only authorized commercial workflows can create or reverse a confirmed sale event.

The platform will also support legitimate returns and transaction corrections, ensuring that the system can represent real commercial activity without treating every repeat scan as evidence of counterfeiting.

### **3.4 Duplicate-identity and anomaly detection**

The platform analyzes verification and transaction events to identify patterns that may indicate QR-code cloning or other misuse.

Examples include:

* The same product identity appearing in geographically distant locations within an implausible time interval.  
* An unusual volume of scans associated with one identity.  
* Repeated scans after a recorded sale.  
* Conflicts between a product's recorded distribution history and its observed activity.  
* Attempts to use invalid, unissued or improperly accessed identifiers.

The system assigns risk levels and provides an explanation of the evidence supporting each alert.

These alerts are investigative signals, not automatic declarations that a physical product is counterfeit. Legitimate repeat scans, returns, shared devices and distribution practices must be considered before an alert is escalated.

### **3.5 Manufacturer intelligence dashboard**

Participating manufacturers receive a dashboard for managing product identities and monitoring product-integrity events.

The dashboard will support:

* Product, batch and unit identity management.  
* QR-code issuance and label export.  
* Batch-level traceability.  
* Retailer and distributor registration.  
* Sales-event coverage and lifecycle monitoring.  
* Suspicious-scan alerts.  
* Geographic and temporal analysis of identity reuse.  
* Investigation notes and alert resolution.  
* Product recalls and relevant manufacturer notices.  
* Reports on verification activity and emerging patterns.

The dashboard converts product verification from a passive lookup service into an operational brand-protection capability.

## **4\. How the Solution Works End to End**

The platform's operating model follows the product from manufacturer issuance to consumer verification.

**Stage 1 — Manufacturer onboarding**

The manufacturer registers, establishes authorized users and registers its product catalogue.

**Stage 2 — Product serialization**

The manufacturer creates a production batch and generates unique identities for its product units, packs and cartons.

**Stage 3 — Packaging and release**

QR codes are printed on the relevant packaging. The manufacturer confirms production and release events according to its authorized workflow.

**Stage 4 — Distribution**

Where participating distributors and retailers use the platform, receipt and transfer events are recorded. The platform maintains the available history of product movement.

**Stage 5 — Retail checkout**

An integrated POS system or the platform's mobile merchant interface records a confirmed sale. The system updates the unit's lifecycle status and retains the transaction event.

**Stage 6 — Consumer verification**

The consumer scans the QR code. The platform checks the registered identity, lifecycle status and relevant risk signals before presenting the result.

**Stage 7 — Risk detection and investigation**

If the identifier appears in conflicting circumstances, the platform raises an alert, presents the available evidence and enables the manufacturer to investigate.

This workflow establishes a connected relationship between the identity assigned at production, the events recorded during distribution and the information available at consumer verification.

The accuracy and completeness of the resulting intelligence depend on participating manufacturers and retailers recording reliable events. The platform must clearly distinguish recorded facts from inferred or unobserved activity.

## **5\. What Makes the Idea Exceptional?**

### **5.1 It moves authentication from product type to individual unit**

The core innovation is not simply assigning a QR code to a product.

It is establishing a digital identity for each individual unit and linking that identity to a record that can evolve throughout the product's lifecycle.

This creates a more precise foundation for investigating suspected counterfeiting than a shared registration number alone.

### **5.2 It connects authentication with the point of sale**

Many verification experiences focus on identifying a product when a consumer scans it.

This platform adds a commercial event layer: the system can learn when an authorized retailer records a product as sold and use that event when evaluating subsequent scans.

The combination of identity and transaction history creates additional evidence for detecting copied identifiers.

This capability depends on transaction coverage, integration quality and the reliability of the participating retail network.

### **5.3 It combines consumer participation with manufacturer intelligence**

Every verification request can contribute useful information about where and when a product identity is being observed.

When analyzed alongside authorized events, this information can help reveal patterns that would be difficult to identify from isolated product lookups.

The consumer interface becomes an entry point into a broader brand-protection intelligence network.

### **5.4 It is designed for both enterprise and informal retail**

The platform does not assume that every retailer has a sophisticated POS system.

Enterprise customers can integrate through APIs, while smaller retailers can use a mobile merchant interface.

This reduces the infrastructure barrier to participation and creates a pathway toward broader distribution coverage.

### **5.5 It creates a foundation for cross-sector expansion**

The identity and event architecture can support multiple eligible product categories, including cosmetics, packaged foods, beverages, personal care and other consumer goods.

The business can reuse much of its core technology while adapting product data, compliance requirements, packaging hierarchies and security measures to each sector.

This provides a potential path from a focused Nigerian pilot to an Africa-first product-integrity platform.

## **6\. Competitive Positioning and Market Edge**

The competitive landscape includes regulatory verification systems, barcode and serialization providers, anti-counterfeit technology companies, product traceability platforms and manufacturers' proprietary solutions.

The platform should not assume that these alternatives are incapable of item-level tracking or counterfeit detection. Its competitive edge must be demonstrated through the combination of capabilities, ease of deployment and measurable commercial value.

### **Proposed differentiation**

**A. Transaction-aware authentication**

Differentiate through the integration of product identity with authorized checkout events and subsequent scan analysis.

**B. Affordable adoption for smaller retailers**

Provide a lightweight mobile merchant workflow alongside enterprise-grade APIs, rather than requiring every participant to purchase sophisticated retail hardware.

**C. Manufacturer-centered risk intelligence**

Focus on turning suspicious activity into useful evidence, including affected identities, associated batches, event timelines and investigation workflows.

**D. Cross-sector product-integrity infrastructure**

Build a reusable core platform that can serve different product categories while accommodating their distinct regulatory and operational requirements.

**E. Interoperability as a future advantage**

Although the initial demonstration may operate independently, the data model should be designed to support established identifiers and relevant industry standards, including GS1-compatible approaches where appropriate.

### **Competitive comparison**

| Capability | Basic registration lookup | Basic QR verification | Proposed platform |
| ----- | ----- | ----- | ----- |
| Registered product information | Yes, where supported | Yes, where configured | Yes |
| Individual unit identity | Not necessarily | Possible | Core capability |
| Transaction-linked status | Not inherent | Not inherent | Core capability |
| Duplicate-scan risk analysis | Varies | Varies | Core capability |
| Mobile merchant checkout | Not inherent | Not inherent | Planned capability |
| Manufacturer investigation dashboard | Varies | Varies | Core capability |
| Cross-sector architecture | Depends on provider | Depends on provider | Strategic design objective |

This is a conceptual comparison, not a verified assessment of every competitor's current features. Before commercial launch, the business should conduct a structured competitor analysis covering local providers, regulatory platforms, global traceability vendors and existing manufacturer solutions.

## **7\. The Biggest Strategic Risk: QR-Code Cloning**

The most important technical risk is that a valid QR code can be copied onto counterfeit packaging.

A copied identifier can initially return a valid product record because the identifier genuinely belongs to a product issued by the manufacturer.

This is the fundamental limitation of static QR-code authentication. A cryptographically random identifier prevents practical guessing of other identifiers, but it does not prevent copying an identifier that is already visible.

If the platform ignores this limitation, it could give consumers false confidence and expose manufacturers to reputational risk.

### **How the architecture mitigates this risk**

**Layer 1 — Unpredictable unique identity**

Each product unit receives a cryptographically random public token with sufficient entropy, such as 128 bits. The token is separate from internal database identifiers and is subject to database uniqueness constraints.

This makes identifier enumeration and accidental collision extremely unlikely.

**Layer 2 — Trusted lifecycle events**

The platform records authorized manufacturing, distribution, checkout, return and other relevant events. Authenticated access, role-based permissions, audit history and transaction controls protect the integrity of the official records.

A consumer scan cannot directly change an item's lifecycle state.

**Layer 3 — Duplicate-scan intelligence**

The system compares scan patterns against transaction history and available location and timing information.

Repeated or geographically conflicting use of one identity can trigger a risk alert, especially when combined with a recorded sale or inconsistent distribution history.

**Layer 4 — Risk-based verification outcomes**

The system distinguishes a recognized identity from a confirmed sale, suspicious activity or an invalid identifier.

It does not automatically label every previously sold item as counterfeit, and it does not claim that a first scan proves physical authenticity.

**Layer 5 — A path to stronger physical authentication**

The initial prototype uses QR codes and backend controls, keeping the demonstration accessible and affordable.

For higher-risk applications, future versions can introduce tamper-evident labels, concealed verification codes, NFC or other physical security measures. These can make it harder to transfer a valid identity to a counterfeit object.

The security architecture is therefore designed to detect and reduce identity abuse now while allowing stronger authentication to be added as commercial needs justify it.

### **Residual risk**

No QR-only system can guarantee detection of every cloned code. A counterfeit package carrying a copied identifier may pass an initial check if the platform has not yet observed conflicting activity.

This limitation should be reflected in product messaging, risk scoring and customer contracts. The objective is to make counterfeit activity more difficult to conceal and easier to investigate, not to promise infallible physical authentication.

## **8\. Other Strategic Risks and Mitigations**

### **Retailer participation and incomplete transaction records**

If retailers do not record sales, the platform may lack the event history required for effective post-sale detection.

**Mitigation:** simplify checkout workflows, support existing POS integrations, offer a mobile merchant interface and measure the percentage of pilot sales captured by the platform.

### **Manufacturer adoption and packaging costs**

Manufacturers may resist changing production workflows or paying for serialization.

**Mitigation:** support practical label-generation workflows, begin with a manageable product range and demonstrate measurable brand-protection value before proposing broad deployment.

### **False-positive alerts**

Legitimate repeat scans, returns and distribution movements can resemble counterfeit activity.

**Mitigation:** use explainable risk levels, context-aware rules and an investigation workflow. Do not present an anomaly as a confirmed counterfeit without supporting evidence.

### **Regulatory and standards alignment**

An independent platform may duplicate existing capabilities or fail to satisfy sector-specific requirements.

**Mitigation:** validate the requirements of the selected pilot sector, design for interoperability and pursue appropriate partnerships or approvals before entering regulated categories.

### **Data privacy and security**

Scan locations, retailer transactions and manufacturer information may be commercially sensitive or personal.

**Mitigation:** collect only necessary data, protect sensitive fields, restrict access by role, establish retention rules, secure integrations and assess applicable Nigerian data-protection requirements.

## **9\. AI and Intelligence Strategy**

Artificial intelligence should enhance the platform's intelligence rather than substitute for the underlying security controls.

The first version should use deterministic validation rules and explainable anomaly detection. These can identify known suspicious conditions without requiring a large training dataset.

As real data becomes available, AI capabilities may include:

* Detecting unusual scan frequencies and geographic patterns.  
* Ranking alerts by estimated risk.  
* Identifying emerging clusters of suspected identity reuse.  
* Correlating product, batch, transaction and distribution events.  
* Helping investigators summarize evidence and prioritize follow-up.

The platform should not use AI alone to declare a product counterfeit. High-impact decisions should remain explainable, reviewable and supported by evidence.

A future intelligence layer could help manufacturers identify recurring patterns across products, retail locations and distribution channels, subject to appropriate data permissions and privacy controls.

## **10\. Target Customers and Revenue Model**

Manufacturers and brand owners are the primary paying customers because they have a direct commercial interest in protecting their brands, improving traceability and investigating suspected counterfeit activity.

Potential revenue streams include:

1. **Manufacturer onboarding fees:** product configuration, data setup and initial deployment.  
2. **Recurring subscriptions:** access to the manufacturer portal, identity management, monitoring and reports.  
3. **Serialization fees:** volume-based charges for issuing and managing unit identities.  
4. **Enterprise integration fees:** POS, ERP, inventory and distribution-system integration.  
5. **Premium intelligence services:** advanced risk analytics, investigation support and brand-protection reporting.  
6. **Enhanced authentication services:** optional physical security labels and related partner services.

Consumer verification should remain free to encourage adoption and generate useful observations.

The initial pricing model should be validated through customer interviews and pilot negotiations rather than established on assumptions alone.

## **11\. Go-to-Market Strategy**

### **Phase 1 — Market validation**

Interview prospective manufacturers and brand owners in selected consumer-product categories.

Validate the frequency and cost of counterfeit incidents, current investigation processes, packaging constraints, willingness to adopt serialization and access to retail transaction data.

### **Phase 2 — Demonstration prototype**

Build the manufacturer portal, unit identity generation, consumer verification page, merchant mobile interface, simulated POS integration and risk dashboard.

Use deliberately cloned identifiers and simulated conflicting scans to demonstrate the system's detection capability.

### **Phase 3 — Controlled manufacturer pilot**

Select one initial product category and secure at least one manufacturer willing to participate. Introduce a limited product range and a manageable group of retailers.

Measure identity issuance, checkout-event coverage, verification completion, suspicious-pattern detection and investigation outcomes.

### **Phase 4 — Commercial launch**

Convert successful pilots into paid manufacturer contracts. Standardize onboarding, pricing, deployment and reporting, then approach similar manufacturers within the same sector.

### **Phase 5 — Expansion**

Extend the platform to additional categories, POS providers and distribution partners. Introduce stronger physical authentication and standards-based integrations where required.

The initial market should be Nigeria, with expansion into other African markets guided by customer demand, local regulation, partner availability and evidence of product-market fit.

## **12\. Demonstration Prototype Scope**

The initial prototype should demonstrate the complete product-integrity workflow without attempting to solve every sector's requirements.

Core capabilities:

* Manufacturer and product registration.  
* Batch creation and unit-level serialization.  
* Cryptographically random public identifiers.  
* QR-code generation and label export.  
* Public consumer verification.  
* Merchant registration and mobile scanning.  
* Simulated POS checkout integration.  
* Sale confirmation and authorized return processing.  
* Product event history.  
* Duplicate-scan detection and risk alerts.  
* Manufacturer dashboard and investigation view.

A successful demonstration should show that a legitimate unit can be issued, recorded as received, sold, scanned again and flagged appropriately when its identity is reused under suspicious circumstances.

It should also demonstrate that ordinary repeat scans and legitimate returns do not automatically result in a counterfeit declaration.

The prototype should not be represented as proof that every physical product carrying a valid QR code is genuine.

## **13\. Success Metrics**

The pilot should measure operational and commercial outcomes, including:

* Percentage of product units with valid issued identities.  
* Percentage of pilot sales captured through integrated checkout workflows.  
* Consumer verification completion rate.  
* Time required to onboard a manufacturer and its products.  
* Detection rate for deliberately simulated cloned-code scenarios.  
* False-positive rate across legitimate repeat scans and returns.  
* Time required to investigate a suspicious identity.  
* Manufacturer satisfaction and willingness to pay.  
* Cost per serialized unit at pilot and projected commercial volumes.

These metrics will help determine whether the platform delivers sufficient value to support a sustainable business.

## **14\. Long-Term Vision**

The long-term ambition is to establish a trusted product-integrity network that connects manufacturers, distributors, retailers and consumers across African markets.

As participation increases, the platform could offer manufacturers a more comprehensive view of product identity and observed lifecycle activity, helping them identify suspicious patterns, respond to incidents and strengthen relationships with legitimate distribution partners.

The platform may also create opportunities for authorized industry partnerships, interoperability with established identification standards and carefully governed intelligence-sharing arrangements.

Its long-term defensibility will depend on more than code generation. It will come from reliable manufacturer relationships, retailer adoption, trusted event records, integration capabilities, effective risk detection and the ability to turn product-level observations into useful commercial intelligence.

## **15\. Conclusion**

The Product Integrity & Authentication Platform addresses an important gap between product registration and individual-item verification.

By assigning unique digital identities to products, linking those identities to authorized lifecycle events, enabling accessible consumer verification and analyzing suspicious reuse, the platform offers manufacturers a practical foundation for strengthening brand protection and product traceability.

Its strongest opportunity is the combination of unit-level identity, transaction-aware verification, affordable retail participation and actionable counterfeit-risk intelligence.

The central technical challenge—QR-code cloning—has been addressed in the architecture through unpredictable identifiers, trusted event records, duplicate-scan intelligence, controlled transaction updates and a roadmap toward stronger physical authentication.

The initial product should be launched with a focused manufacturer pilot, measurable success criteria and transparent security claims. Expansion should follow demonstrated customer value and sector-specific validation.

**The strategic ambition is clear: make every product identity accountable, make suspicious product activity more visible, and give manufacturers and consumers better evidence on which to base decisions.**

## ***What does an unpredictable, unique identity mean?***

*Every individual product unit receives a unique identifier that is difficult to guess or generate independently.*

*Imagine a manufacturer produces 100,000 bottles of cooking oil.*

*Instead of assigning identifiers like:*

* *`OIL-000001`*  
* *`OIL-000002`*  
* *`OIL-000003`*

*—which expose a predictable sequence—you generate a random identifier for each unit, such as:*

*`https://verify.example.com/p/K7mQ9xV2nR8wB4cL6tY3gA`*

*These are illustrative values, not live verification codes.*

*The QR code encodes the verification URL, and the identifier after `/p/` points to one specific product unit in your database.*

*The key principle: knowing one valid identifier should not help someone guess another valid identifier.*

## ***2\. How I would generate the identifiers***

*Use a cryptographically secure random number generator (CSPRNG), not a timestamp, sequential database ID, or ordinary random function.*

*A practical default is 128 bits of cryptographically secure randomness, encoded using Base64url or another URL-safe encoding.*

*Step 1 — Manufacturer creates a batch*

*Example: cooking oil, 500 ml, Batch B-2026-014.*

*Step 2 — Generate a random public token for each unit*

*Each token is independent, unique in the database*

*continue*

*and infeasible to guess at scale.*

*Step 3 — Generate the QR code*

*Encode the verification URL containing the public token and print it on the individual product.*

*Step 4 — Register the identity*

*Store the token or its cryptographic hash against the internal unit record, manufacturer, product, batch, and lifecycle status.*

## ***3\. Keep the public identifier separate from the internal ID***

*Your database should distinguish between the internal record and the public verification token.*

| *Field* | *Example* | *Purpose* |
| ----- | ----- | ----- |
| *`unit_id`* | *`847291`* | *Internal database primary key* |
| *`public_token_hash`* | *SHA-256 hash of the token* | *Supports token lookup without storing the raw token* |
| *`manufacturer_id`* | *`MFR-1042`* | *Links to the manufacturer* |
| *`product_id`* | *`PROD-208`* | *Links to the product type* |
| *`batch_id`* | *`BATCH-014`* | *Links to the production batch* |
| *`lifecycle_status`* | *`IN_CIRCULATION`* | *Current recorded operational status* |

*The public token must not be derived from `unit_id`, because that would reintroduce predictability.*

*For additional protection, the application can store a SHA-256 hash of the randomly generated token and calculate the hash of a submitted token when it is scanned. Since the token has high entropy, this is a practical approach to protecting stored identifiers.*

## ***4\. How much randomness do you need?***

*Here is why 128 bits is a good default.*

*A 128-bit random identifier has ${2}^{128}$ possible values, approximately $3.4\times 1{0}^{38}$.*

*Even if your platform eventually issues one billion product identities, the probability of an accidental collision is approximately:*

*$P\approx \frac{n(n-1)}{2\times {2}^{128}}$*

*For $n=1{0}^{9}$, that is approximately $1.47\times 1{0}^{-21}$.*

*This is extraordinarily small. Nevertheless, enforce a database uniqueness constraint and retry generation if a collision ever occurs.*

## ***5\. Recommended implementation logic***

*Here is illustrative Python code for generating a URL-safe public token.*

*import secretsimport hashlibdef generate\_product\_identity():    \# 128 bits of cryptographically secure randomness    token \= secrets.token\_urlsafe(16)    \# Store the hash, not the raw public token    token\_hash \= hashlib.sha256(token.encode("utf-8")).hexdigest()    verification\_url \= f"https\://verify.example.com/p/{token}"    return {        "public\_token": token,        "public\_token\_hash": token\_hash,        "verification\_url": verification\_url,    }*

*This code generates an identity; it does not yet save it to a database, generate a QR image, or implement authentication. In production, persist the token hash and product metadata atomically, enforce uniqueness, and handle collisions by generating a new token.*

*Also, keep the public verification endpoint rate-limited and monitor automated scanning. Random identifiers make enumeration much harder, but they do not stop someone from copying a QR code that they can physically see.*

## ***6\. One distinction that matters for your platform***

*A random token provides an unpredictable identity. It does not by itself prove that a product carrying that token is genuine.*

*Your complete verification decision should combine:*

* *Whether the identifier was issued by an authorized manufacturer.*  
* *Whether the identity's digital record is valid.*  
* *Whether the product's lifecycle events are consistent.*  
* *Whether scan patterns indicate possible copying or misuse.*

*For the demonstration prototype, I recommend 128-bit random public tokens, hashed storage, a database uniqueness constraint, and a verification URL that exposes no internal database identifiers.*

*That gives you a sound foundation for the remaining layers: event history, transaction-linked status, and duplicate-scan intelligence.*

