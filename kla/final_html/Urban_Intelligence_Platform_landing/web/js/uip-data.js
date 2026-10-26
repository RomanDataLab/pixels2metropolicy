/* Urban Intelligence Platform — page content (pipeline from "urban platform scheme") */
window.UIP = (function () {
  const PIPE = [
    { id: "seg", kind: "tool", no: "01", title: "Satellite segmentation tool", brief: "Rooftops segmented; blobs of dense, small, aligned roofs become settlement candidates.", long: "A segmentation model (SAM-Geo → U-Net lineage, trained on THEOS chips) outlines every rooftop. Morphology then clusters roofs into blobs using density, size variance, orientation concentration and canal proximity; accepted blobs become settlement candidates with quarterly re-runs so each community carries its own density time-series.", sources: ["THEOS-2 scenes (quarterly 0.5 m epochs)", "Segmentation models: Gen1 SAM-Geo / Gen2 U-Net / Gen3", "Blob acceptance rules (density, size CV, orientation, canals)"], sec: "seg" },
    { id: "match", kind: "tool", no: "02", title: "Match to regular properties", brief: "Candidates matched to parcels and zones; mismatches flagged as irregular.", long: "Each candidate blob is matched against the regular-property layer: overlay with parcels, plan zones and regulation. A blob that conforms to the plan is regular. A blob with no tenure record, in violation of plan use, or absent from the cadastre is flagged as a true irregular block — with the matching evidence attached.", sources: ["Cadastre parcels (land department)", "Comprehensive-plan zones (BMA)", "Masterplan, municipal regulation & district plans"], sec: "match" },
    { id: "social", kind: "tool", no: "03", title: "Social sensing tool", brief: "Datalake filtered by domain, quality-checked, scored per community.", long: "The tool's urban datalake is updated daily from heterogeneous feeds — Thai and English news RSS, the Traffy Fondue complaint channel, national public traffic cameras, traffic-event feeds and official statistics. Events are filtered into domains — environment hazard, basic services, crime & security, informal economy, contamination, social support, housing tenure risk, destitution, flooding, fires — then geographically attached to communities, quality-checked and scored. A cumulative ranking of irregular neighborhoods emerges from the filtered signal, not from a stale census.", sources: ["Urban datalake: news RSS (TH/EN), Traffy Fondue, public traffic cameras, traffic events, official statistics", "Domain classifiers (10 domains)", "Community polygon gazetteer"], sec: "social" },
    { id: "rank", kind: "tool", no: "04", title: "Ranked irregular neighborhoods", brief: "Map and table: where informal-city pressure concentrates.", long: "Every irregular neighborhood carries a cumulative score with per-domain sub-scores. The ranking is browsable as a map (solo or bivariate against building density) and as a sortable table — the agenda for the rest of the pipeline.", sources: ["Social sensing scores", "Segmentation density series"], sec: "social" },
    { id: "priority", kind: "tool", no: "05", title: "Priorities + area selection", brief: "Prioritization by feasibility × severity; intervention areas selected.", long: "Ranked neighborhoods are crossed with feasibility — land status, budget windows, agency capacity — to produce priority classes. High-severity, feasible areas are selected for intervention; infeasible-but-severe areas stay on a watch list with their score trend.", sources: ["Ranked irregular neighborhoods", "Feasibility layers (tenure, budget, capacity)"], sec: "priority" },
    { id: "participate", kind: "tool", no: "06", title: "Participation techniques", brief: "Cards grouped by participation class; techniques chosen per area.", long: "For each selected area the platform proposes a participation package from a pool of techniques classified on the Arnstein / IAP2 ladder — inform, consult, involve, collaborate, empower — plus an extra-institutional risk class that is monitored, never planned. Classes 3–5 are the operable pool; the kit sets minimum and ceiling.", sources: ["49-case slum policies review (31 countries)", "Thai institutional channels (Baan Mankong/CODI, Traffy Fondue, youth councils)", "Arnstein 1969; IAP2 spectrum"], sec: "participate" },
    { id: "kits", kind: "tool", no: "07", title: "Urban governance kit", brief: "One kit of actions + techniques selected per intervention.", long: "Six policy kits — collective in-situ upgrading, re-blocking, land sharing, risk-first retrofit, street-economy legitimization, relocation with dividend — assemble proven program components into a dispatch table. The kit fixes the action list and the participation floor and ceiling for the intervention.", sources: ["Policy kits (proposal)", "Dispatch table: score signature → kit"], sec: "kits" },
    { id: "design", kind: "tool", no: "08", title: "Design + approval", brief: "Intervention strategy designed, layered, approved with the community.", long: "The chosen kit becomes a concrete intervention strategy: a map of changes — fire lanes, re-blocked plots, common-use areas, market zones — each location tied to a component card. The strategy passes through the selected participation techniques to approval, then enters the intervention program.", sources: ["Kit actions", "Participation package", "Intervention program register"], sec: "design" },
    { id: "program", kind: "out", no: "→", title: "Urban intervention program", brief: "Approved interventions enter execution.", long: "Approved strategies are programmed: budget lines, agency assignments, community contracts and quarterly monitoring against the same satellite + datalake evidence that selected them.", sources: ["Approved strategies"], sec: "design" },
    { id: "assess", kind: "feed", no: "↺", title: "Assessment of result", brief: "Outcome re-enters the datalake; the loop closes.", long: "After-action assessment reads roof change, complaint closure and event decay from the same pipeline — closing the loop back into the datalake so the next prioritization round starts from measured results, not promises.", sources: ["Roof-density epochs", "Traffy Fondue closure rates", "Domain event decay"], sec: "social" },
  ];

  const VIDEOS = {
    seg: { src: "media/p2m-fire-makkasan.mp4", tag: "theos · makkasan", note: "Fire in a dense informal block — the fabric the segmentation tool maps rooftop by rooftop." },
    match: { src: "media/clip-flood.mp4", tag: "datalake · flood clip", note: "Flood clip ingested by the datalake — geocoded, domain-tagged, joined to communities." },
    social: { src: "media/clip-street.mp4", tag: "datalake · street", note: "Street life is a signal: vending and popup markets feed the informal-economy domain." },
    rank: { src: "media/clip-fire.mp4", tag: "datalake · fire", note: "Fire events are a ranking input — technical-disaster domain, weighted into the cumulative score." },
    priority: { src: "media/p2m-flood-lat-krabang.mp4", tag: "priority · lat krabang", note: "Repeated flooding on the east bank pushes an area up the priority classes." },
    participate: { src: "media/clip-street.mp4", tag: "participation · street", note: "Participation starts where people already are — the street economy the platform senses daily." },
    kits: { src: "media/clip-flood.mp4", tag: "kits · flood retrofit", note: "Kit choice follows the score signature — flood signal first, kit 4 risk-first retrofit." },
    design: { src: "media/walkthrough.mp4", tag: "strategy walkthrough", note: "The full walkthrough: from pixels to a designed, approved intervention strategy.", poster: "media/p2m-flood-poster.jpg" },
    program: null, assess: null,
  };

  // process steps per section
  const PROC = {
    seg: [["Acquire", "Quarterly THEOS-2 scene, orthorectified, tiled into chips"], ["Segment", "Roof-outline model infers per-building polygons with confidence"], ["Morphology", "Roofs clustered: density/ha, size CV, orientation, canal proximity"], ["Accept blobs", "Rules accept or reject each blob as a settlement candidate"], ["Time-series", "Blob re-run each epoch; density change becomes a signal"]],
    match: [["Load regularity", "Parcels, comprehensive-plan zones, regulation as one layer"], ["Overlay", "Candidate blobs intersected with the regular-property layer"], ["Test rules", "Conforming use? parcel record? tenure evidence? plan violation?"], ["Flag irregular", "Mismatches become true irregular blocks with evidence attached"], ["Publish", "Matched layer feeds the social sensing and ranking stages"]],
    social: [["Ingest daily", "News RSS, Traffy Fondue, cameras, traffic events, statistics"], ["Geocode", "Every item located and attached to a community polygon"], ["Filter domains", "Ten domains: hazard, services, crime, economy, contamination…"], ["Quality check", "Duplicates, rumors and stale items removed before scoring"], ["Score + rank", "Per-domain intensity → cumulative neighborhood ranking"]],
    priority: [["Score severity", "Cumulative rank + domain sub-scores per irregular block"], ["Weigh feasibility", "Tenure status, budget window, agency capacity, land value"], ["Classify", "P1 act now · P2 program · P3 monitor · P4 watch"], ["Select areas", "P1/P2 areas selected; the rest keep their trend line"]],
    participate: [["Read the kit", "Each kit sets a participation floor and ceiling"], ["Pick the pool", "Classes 3–5 operable; 1–2 context; 6 monitored risk"], ["Match context", "Thai channels (CODI, Traffy, youth councils) where they exist"], ["Assemble package", "Techniques per area, with failure modes checked"]],
    kits: [["Score signature", "Rank + domain sub-scores form the area signature"], ["Dispatch table", "Signature → primary kit + fallback (score signature table)"], ["Assemble", "Actions + participation techniques from the kit menu"], ["Commit", "One kit per intervention — components, budget, monitoring"]],
    design: [["Strategy map", "Kit actions placed: fire lanes, plots, common-use, markets"], ["Component cards", "Each location tied to an image card with its description"], ["Participation gate", "Selected techniques run before works are fixed"], ["Approve + program", "Approved strategy enters the intervention program"]],
  };

  // rollups: [full description, data sources list]
  const ROLLUP = {
    seg: ["The segmentation tool turns quarterly THEOS-2 imagery into a living census of informal roofs. A model lineage that started with SAM-Geo prompts, moved through a U-Net trained on labeled chips, and now runs batch inference over the whole metropolis outlines each rooftop with area, perimeter and confidence. Morphological rules then group roofs into settlement-candidate blobs: density per hectare, size variation, orientation concentration and distance to canals decide acceptance. Accepted blobs are re-segmented every quarter, so each settlement carries a density time-series — growth, clearance and fire scars are measured, not reported.",
      ["GISTDA THEOS-2 / THEOS-1 archive (quarterly epochs)", "Segmentation models: Gen 1 SAM-Geo, Gen 2 U-Net, Gen 3 (this repo)", "Blob rules: density_ha, size CV, orientation concentration, canal distance", "QA chips + prefill batches (labeling workspace)"]],
    match: ["Matching is where two cities meet: the informal city the satellite sees and the regular city the registers describe. Cadastral parcels, comprehensive-plan zones and municipal regulation are overlaid with each settlement candidate. Conformance is tested rule by rule — use against the plan zone, parcel existence, tenure record. A candidate that conforms drops out as regular settlement. A candidate that violates the plan, sits on unregistered land or lacks any record is flagged as a true irregular block, and the matching evidence travels with it into ranking and prioritization.",
      ["Cadastre (land department parcels)", "Comprehensive-plan zones (BMA)", "Municipal regulation & district plans", "Metropolitan strategies"]],
    social: ["The social sensing tool keeps the platform alive between satellite epochs. A datalake is updated daily from news RSS in Thai and English, the Traffy Fondue complaint channel, public traffic cameras, traffic-event feeds and official statistics. Items are geocoded, attached to community polygons and filtered into domains — environmental hazard, basic services, crime & security, informal economy, contamination, social support, housing tenure risk, destitution, flooding, fires. After a quality-check pass (duplicates, rumors, staleness) each community receives per-domain intensities and a cumulative rank. Irregular neighborhoods from the matching stage are then ranked on the map — solo, or bivariate against building density — and in a sortable table.",
      ["Urban datalake: news RSS (TH/EN), Traffy Fondue, traffic cameras, traffic events, official statistics", "Domain taxonomy (10 domains)", "Community polygon gazetteer (1,993 communities)", "Segmentation density series (bivariate axis)"]],
    priority: ["Prioritization turns a ranking into an agenda. Severity comes from the cumulative score and its domain sub-scores; feasibility comes from tenure status, budget windows, agency capacity and land value. Crossing the two produces priority classes — P1: act now; P2: program; P3: monitor; P4: watch — visualized as colors on the irregular blocks. Selected P1/P2 areas proceed to participation and kit selection; everything else keeps its trend line so nothing disappears silently.",
      ["Ranked irregular neighborhoods (social sensing)", "Feasibility layers: tenure, budget, capacity, land value", "Selection rules documented per round"]],
    participate: ["Before any intervention is designed, the platform selects how the community will take part. The pool is a card deck of techniques extracted from a 49-case review of slum policies across 31 countries, classified on Arnstein's ladder and the IAP2 spectrum, and extended with techniques that already operate in Thailand — Baan Mankong enumerations and savings groups, Traffy Fondue with write-back, statutory public hearings, district youth councils, participatory planning under the Decentralization Act. Cards are grouped by class color; each kit fixes a minimum and a ceiling. Classes 3–5 are the operable pool; class 6 is monitored as a leading indicator of failure, never planned.",
      ["49-case slum policies review (31 countries)", "Arnstein (1969); IAP2 spectrum", "Thai institutions: CODI/Baan Mankong, Traffy Fondue (BMA), EIA hearings, Youth Councils Act B.E. 2560, Decentralization Act B.E. 2542"]],
    kits: ["The governance kit is the platform's policy vocabulary: six packages of actions assembled from proven programs. KIT 1 collective in-situ upgrading (Baan Mankong lineage); KIT 2 minimal re-blocking + infrastructure (Kampung Improvement lineage); KIT 3 land sharing / readjustment (Mukuru SPA, Thai land-sharing); KIT 4 risk-first retrofit (Favela-Bairro, Medellín PUI); KIT 5 street-economy legitimization; KIT 6 relocation with common-use dividend. A dispatch table maps the area's score signature to a primary kit and a fallback. Each kit carries an action list and a participation floor and ceiling; the interactive scheme shows every kit connected to its techniques by bezier lines.",
      ["Policy kits (proposal §4)", "Score signature → kit dispatch table", "Participation matrix (kit × class)"]],
    design: ["Design and approval is where evidence becomes a strategy. The selected kit's actions are placed on the map as layers of change — a fire lane cut through dense fabric, re-blocked plots, a common-use area on vacated land, a market zone for the street economy — and each location is connected to a component card that flips to its description. The strategy passes through the chosen participation techniques (the gate), is revised with the community, and on approval enters the urban intervention program with budget lines and quarterly monitoring. The result is then assessed by the same pipeline — closing the loop.",
      ["Kit actions + participation package", "Intervention program register", "After-action assessment (roofs, complaints, events)"]],
  };

  // participation cards (from participation.html, 49-case review)
  const PART_CLASSES = [
    { n: 1, name: "Inform", color: "var(--p1)", img: "img/part/class1.jpg" },
    { n: 2, name: "Consult", color: "var(--p2)", img: "img/part/class2.jpg" },
    { n: 3, name: "Involve / co-produce", color: "var(--p3)", img: "img/part/class3.jpg" },
    { n: 4, name: "Collaborate / co-decide", color: "var(--p4)", img: "img/part/class4.jpg" },
    { n: 5, name: "Empower", color: "var(--p5)", img: "img/part/class5.jpg" },
    { n: 6, name: "Extra-institutional (risk)", color: "var(--p6)", img: "img/part/class6.jpg" },
  ];
  const PART_CARDS = [
    { c: 1, t: "Showcase social programming", d: "Visibility events and social programmes delivered alongside mega-works, communicated to rather than shaped by residents. Participation in name; information in practice.", tags: ["PAC · Complexo do Alemão, Rio"] },
    { c: 1, t: "Mandated consultation, in practice", d: "Consultation legally required by the upgrading programme (UISP) but executed as one-way notice once budgets are locked — the formal floor every project must exceed.", tags: ["UISP · South Africa"] },
    { c: 2, t: "Design contests per settlement", d: "Architectural competitions run per favela, with entries exhibited to residents. Opens design options; decision frame stays with the state.", tags: ["Favela-Bairro · Rio"] },
    { c: 2, t: "Residents vote on proposals", d: "Intervention options put to a resident vote before works are scheduled. Pair with enumeration so the option set itself reflects resident data.", tags: ["Favela-Bairro / Morar Carioca"] },
    { c: 2, t: "Infrastructure design workshops", d: "Community workshops on station and facility design for transit-led projects. Cheap, fast, improves acceptance — but scope stays fixed.", tags: ["TransMiCable · Bogotá"] },
    { c: 2, t: "Household compensation negotiation", d: "Relocation compensation negotiated household by household with no community-level planning. Kept in the pool as a caution: it fragments voice.", tags: ["Canal resettlement · HCMC"] },
    { c: 2, t: "Statutory public hearings (ประชาพิจารณ์)", d: "Legally required public hearings under EIA and related notification rules. Formalistic alone — always pair with enumeration or a survey round.", tags: ["TH", "EIA rules · Thailand"] },
    { c: 2, t: "Works notice + layout vote", d: "Minimum viable participation for quick re-blocking: residents notified, then vote on the block layout (fire lanes, water points) before machinery moves.", tags: ["KIT 2"] },
    { c: 2, t: "Vendor committee consultation", d: "Street-vendor committees consulted on permit zones, market days and sanitation rules before street-economy regularization is fixed.", tags: ["KIT 5"] },
    { c: 3, t: "Resident-run house enumerations", d: "Residents count and map their own households — the evidence base tenure negotiation and infrastructure design rest on. Cheaper and better-trusted than contractor surveys.", tags: ["Kibera · Nairobi", "South Africa UISP"] },
    { c: 3, t: "City-wide community surveys", d: "Community organizations survey all settlements city-wide, producing the register the programme then finances. Baan Mankong's entry gate — a Thai class-3 export.", tags: ["TH", "Baan Mankong · CODI", "KIT 1"] },
    { c: 3, t: "Consortium plan co-writing", d: "A consortium of 40+ community organizations and NGOs co-writes the special planning area plan — the settlement's own plan becomes the statutory document.", tags: ["Mukuru SPA · Nairobi", "KIT 3"] },
    { c: 3, t: "Women's issue campaigns", d: "\"Too Pressed to Wait\": women organized around shared-sanitation failures, produced the demand data, and moved sanitation up the plan's priority order.", tags: ["Mukuru SPA · Nairobi"] },
    { c: 3, t: "Resident mapping of evacuation routes", d: "Residents walk and map their own evacuation routes, fire breaks and flood spots — local knowledge that risk-first retrofit designs around.", tags: ["KIT 4"] },
    { c: 3, t: "Digital complaints with write-back", d: "Traffy Fondue: government-run city-scale complaint channel, already ingested by the pipeline. Upgrades toward class 3 when ticket status is written back within days.", tags: ["TH", "Traffy Fondue · BMA"] },
    { c: 3, t: "District youth councils", d: "Mandatory district-level youth councils under the Children and Youth Councils Act B.E. 2560 (2017) — a statutory channel for young residents.", tags: ["TH", "Youth councils · B.E. 2560"] },
    { c: 4, t: "Participatory budgeting of project shares", d: "Residents allocate a defined share of project budgets across neighbourhoods. The most-copied Medellín mechanism; needs real money on the table.", tags: ["PUI · Medellín"] },
    { c: 4, t: "Committees co-decide works sequence", d: "Community committees decide in what order streets, drainage and housing get done — trading off against their own constraints, not the contractor's.", tags: ["Paraisópolis · São Paulo", "KIT 2"] },
    { c: 4, t: "Youth co-design of public space", d: "Young residents co-design parks, libraries and sports facilities as equity tools, not decoration — the social-urbanism signature.", tags: ["Comuna 13 · Medellín"] },
    { c: 4, t: "Associations as service providers", d: "Neighbourhood associations contract and deliver services themselves, not just advise. Fragile: Rio's contracted meetings were cut in 2013 and trust followed.", tags: ["Rocinha · Rio"] },
    { c: 4, t: "Participatory local planning rounds", d: "Annual participatory planning mandated by the Decentralization Act B.E. 2542 (1999) — the formal slot where community priorities enter district plans.", tags: ["TH", "Decentralization Act 2542"] },
    { c: 4, t: "Pracha-rath partnership", d: "State–private–people (ประชารัฐ) coordinating framework: private-sector participation brokered with community consent rather than around it.", tags: ["TH"] },
    { c: 4, t: "Khlong Toei community interlocutors", d: "Experienced community organizations (Duang Prateep lineage; NHA–port-authority committees) that can hold a negotiation across years.", tags: ["TH", "Khlong Toei · Bangkok", "KIT 3"] },
    { c: 4, t: "Vendor co-management of market days", d: "Street vendors co-manage market days, permits and sanitation rules — the ceiling for street-economy legitimization.", tags: ["KIT 5"] },
    { c: 4, t: "Co-decided relocation package", d: "Relocation package (unit mix, transport continuity, timing) co-decided with residents — the non-negotiable floor for KIT 6, not a ceiling.", tags: ["KIT 6"] },
    { c: 4, t: "Co-decided retrofit package", d: "Residents co-decide the risk-reduction package (flood-proofing, fire breaks, slope works, routes) against their own risk ranking.", tags: ["KIT 4"] },
    { c: 5, t: "Collective tenure + direct subsidy", d: "Subsidy paid straight to the community group, which negotiates tenure collectively. The Baan Mankong core: 142,254 households, 1,246 projects, 75 provinces.", tags: ["TH", "Baan Mankong · CODI", "KIT 1"] },
    { c: 5, t: "Community savings groups", d: "กลุ่มออมทรัพย์เพื่อการผลิต — savings groups that pool credit and repayments, giving the community a balance sheet landlords and banks must negotiate with.", tags: ["TH", "Baan Mankong / SDI", "KIT 1"] },
    { c: 5, t: "Collective land negotiation", d: "The community, organized and enumerated, buys or leases land as one counterparty — the ceiling for land sharing and the difference between negotiation and eviction defense.", tags: ["TH", "Baan Mankong · CODI", "KIT 3"] },
    { c: 5, t: "Board seats for the poor", d: "CODI's board reserves seats for community representatives — institutionalized class-5 voice where programmes are designed, not just delivered.", tags: ["TH", "CODI"] },
    { c: 5, t: "Federation co-production", d: "The Shack Dwellers Federation co-produces settlements with the state: enumeration, land, housing, with the federation as delivery partner.", tags: ["Namibia"] },
    { c: 5, t: "Anti-eviction organizing", d: "Decades of organizing that forced the declaration of a Special Planning Area over 645 acres — power that predates and outlasts any single programme.", tags: ["Mukuru · Nairobi"] },
    { c: 5, t: "Cooperative-managed common use", d: "The relocated community's cooperative owns and manages the common-use area and its dividend — the standing KIT 6 component.", tags: ["KIT 6"] },
    { c: 6, t: "Protest as the de facto channel", d: "Where formal channels fail, protest becomes how settlements are heard. Tracked as a leading indicator that classes 1–2 participation failed — not a technique to plan on.", tags: ["South Africa"] },
    { c: 6, t: "Gang mediation", d: "Armed groups shaping which works happen and where. Recorded because it is real; never selected — its presence marks a governance failure to escalate.", tags: ["Rio de Janeiro"] },
  ];

  const KITS = [
    { n: 1, name: "Collective in-situ upgrading", thai: "บ้านมั่นคง 2.0", img: "img/kits/kit1-seggoogle.jpg",
      prec: "Baan Mankong, CODI Thailand — from 2003; community-planned upgrading with infrastructure subsidy + collective loans. Reported 100,000+ households.",
      actions: ["Collective tenure negotiation (lease / co-op)", "Infrastructure subsidy to community organization", "Housing credit through savings group", "Community-managed construction, 9–24 months"],
      tmin: 3, tmax: 5, teqs: ["City-wide community surveys", "Community savings groups", "Collective land negotiation"],
      trigger: "Stable settlement, high complaint backlog, willing CBO, landowner identifiable." },
    { n: 2, name: "Minimal re-blocking + infrastructure", thai: "", img: "img/kits/kit2-roofs.jpg",
      prec: "Kampung Improvement Program, Jakarta — from 1969; paved footpaths, drainage, water points; reached millions nationwide.",
      actions: ["Fire lanes through dense fabric", "Drainage + water points + toilets", "Lighting and waste collection", "Housing stays resident-built; visible in weeks"],
      tmin: 2, tmax: 4, teqs: ["Works notice + layout vote", "Committees co-decide works sequence"],
      trigger: "Roof density above threshold + fire/technical-disaster events + narrow-lane fabric." },
    { n: 3, name: "Land sharing / readjustment", thai: "", img: "img/kits/kit3-criteria.png",
      prec: "Thai land-sharing practice + Mukuru SPA, Nairobi (2017, ≈645 acres, ~100k households, consortium planning).",
      actions: ["Landowner deal: part commercialized, part secured", "On-site rehousing at viable density", "Cadastre check + value appraisal", "Longest kit: 2–5 years"],
      tmin: 3, tmax: 5, teqs: ["Consortium plan co-writing", "Collective land negotiation", "Khlong Toei interlocutors"],
      trigger: "High land value (commercial/mixed zone) + eviction-pressure signal in news." },
    { n: 4, name: "Risk-first retrofit", thai: "", img: "img/kits/kit4-flood.webp",
      prec: "Favela-Bairro, Rio (IDB ≈US$180M) + Medellín PUI: infrastructure + public space to integrate informal areas.",
      actions: ["Flood-proofing", "Fire breaks + slope works", "Evacuation routes", "Anchored on risk registry + repeated-flood layer"],
      tmin: 3, tmax: 4, teqs: ["Resident mapping of evacuation routes", "Co-decided retrofit package"],
      trigger: "Natural-disaster sub-score high + inside repeated-flood zone or risk registry." },
    { n: 5, name: "Street-economy legitimization", thai: "", img: "img/kits/kit5-density.webp",
      prec: "Street-vendor licensing + popup-market programs (Bangkok, Medellín, Seoul night-market regularization).",
      actions: ["Vending permits", "Market days + popup markets", "Sanitation + waste service for markets", "Micro-credit for vendors"],
      tmin: 2, tmax: 4, teqs: ["Vendor committee consultation", "Vendor co-management of market days"],
      trigger: "Street-retail sub-score high AND vending-related complaints rising — vitality with friction." },
    { n: 6, name: "Relocation + common-use dividend", thai: "", img: "img/kits/kit6-heat.webp",
      prec: "CODI relocations; contrast case: pre-Baan-Mankong clearances deepened poverty.",
      actions: ["Near-site units", "Transport continuity", "Rebuilt common-use area on vacated land", "Cooperative-owned dividend; no bare relocation"],
      tmin: 4, tmax: 5, teqs: ["Co-decided relocation package", "Cooperative-managed common use"],
      trigger: "Sensitive zone with no retrofit option + disaster exposure — never land value alone." },
  ];

  const DOMAINS = [
    { id: "nd_", name: "Natural disaster", color: "#3fa2ff" },
    { id: "td_", name: "Technical disaster / fire", color: "#ffb547" },
    { id: "ti", name: "Traffic incident", color: "#9a7bff" },
    { id: "cr", name: "Crime & security", color: "#ff5a4e" },
    { id: "sr", name: "Street retail / popup", color: "#2fd5a5" },
    { id: "bh", name: "Begging / homeless", color: "#c9a227" },
  ];

  return { PIPE, VIDEOS, PROC, ROLLUP, PART_CLASSES, PART_CARDS, KITS, DOMAINS };
})();
