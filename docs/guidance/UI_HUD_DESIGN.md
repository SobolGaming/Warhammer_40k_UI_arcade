# Designing a HUD for Simulated Warhammer 40,000 Tabletop Play

## Rule context

The safest way to design this HUD is to target **stable information classes**, not a single frozen rules snapshot. The current 11th-edition materials show a ruleset built around clearer referencing, updated army construction, mission decks, terrain-aware objectives, and faction detachments; at the same time, 10th-edition systems remain the best fully mature baseline for how information is actually consumed in play. In practice, both editions revolve around the same core UI burdens: players must track turn state, mission state, command resources, attack resolution, unit datasheets, army construction choices, stratagem windows, and battlefield control. What changes between editions is mostly **how those classes are enforced**, not whether they exist. citeturn24view0turn20view0turn21view0turn32view0

In 10th edition, army building and play already bundle together the core classes your HUD must support: a faction and detachment, a roster of units, enhancements, stratagems, a warlord, primary and secondary missions, battle formations, deployment, reserves, and then five battle rounds of scoring. The official 10th army-building article also makes an important interface point explicit: Games Workshop described index cards and the app as tools that collect rules and datacards “in one place for easy reference,” which strongly validates a card-first HUD rather than a text-heavy rules browser. citeturn43view0turn43view1turn40view3turn27view1

The 11th transition keeps those same classes but raises the premium on contextual presentation. Army construction now uses **Detachment Points**, **Enhancement limits**, and **Unit Limits**, and detachments can carry **Force Dispositions** that shape the mission itself. The new Chapter Approved deck introduces five Force Dispositions, 15 mission matchups, refreshed Secondary cards, persistent card-holding decisions, terrain-aware objectives, and optional Twists. That makes the game even more dependent on showing the **right rules at the right moment**, rather than surfacing the whole rules corpus at once. citeturn42view0turn42view2turn42view3turn41view1turn41view4turn41view5turn26view0turn26view3

## Information classes and reference cadence

At the mechanical level, Warhammer 40,000 is a repeated sequence of **Command, Movement, Shooting, Charge, and Fight** phases. The official quick-start guide also exposes why the game feels information-dense in real time: the Command phase refreshes command points and resolves Battle-shock; the Shooting phase proceeds one unit at a time; and attacks are resolved through a fixed pipeline of **Hit roll, Wound roll, Allocate attack, Saving throw, and Inflict damage**. Weapon profiles encode range, number of attacks, hit threshold, strength, armor penetration, and damage, while unit datasheets carry core stats such as Move, Toughness, Save, Wounds, Leadership, and Objective Control. That means the most frequently referenced information is not deep lore text; it is compact operational data tied directly to action resolution. citeturn37search0turn36search2turn34search2turn31search0turn28search2

This density is amplified by stratagem timing and reroll mechanics. Core stratagems can trigger in many phases, and **Command Re-roll** alone can modify hit rolls, wound rolls, damage rolls, saving throws, advance rolls, charge rolls, hazardous tests, and even rolls for number of attacks. Faction examples from the 11th Aeldari preview show additional phase-specific windows: one stratagem keys off a Vehicle falling back in the Movement phase, another off Rangers having already shot in the Shooting phase, another off an enemy ending a move near Harlequins in the opponent’s Movement phase, and another secures an objective at the end of your Movement phase. In other words, the player is constantly asking not only “what are my options?” but “what is legal **right now**, for **this unit**, in **this phase**?” citeturn37search0turn44view0turn44view3turn44view4

Mission information is also much more active than it first appears. In 10th tournament play, players still need to read a Primary Mission, place objective markers, choose Fixed or Tactical Secondaries, draw Tactical cards in the Command phase, and optionally discard or replace cards via New Orders. In 11th, mission data becomes even more live: Force Dispositions determine asymmetric primaries, the mission deck contains 15 matchup combinations, players draw two new secondary missions every Command phase, may hold unscored cards longer, and face round and game scoring caps. So mission information is not merely “pre-game setup”; it is one of the main things players revisit throughout the battle. citeturn40view3turn40view2turn41view0turn41view1turn41view2turn41view3turn41view4

By contrast, the full army roster, complete loadout text, enhancement details, reserves declarations, and attachment structure are referenced less continuously. They matter a great deal, but usually in bursts: list review before battle, leadership/bodyguard checks, reserve arrival, loadout confirmation, or a deeper rules dispute. That is classic **inspect-on-demand** information, not persistent glance information. The fact that 10th/11th official materials repeatedly frame cards, apps, and compact detachment packets as “easy reference” tools reinforces this distinction between high-frequency operational data and lower-frequency inspection data. citeturn27view1turn43view0turn42view4

## Priority breakdown

The breakdown below is the most useful way to think about HUD priority for a simulated tabletop implementation.

- **Persistent glance layer.** This is the information players need almost continuously and should never have to hunt for: active player, round, phase, timer, score, command points, active primary objective summary, active secondary card count or hand state, and a clear marker of whose turn it is. These are operational-dashboard elements: they support time-sensitive decision making and need to be readable at a glance. citeturn35view3turn37search0turn41view2

- **Activation layer.** This is the information needed almost every time a unit is selected: compact selected-unit stats, currently relevant weapons, current target comparison, movement/charge eligibility, visible rerolls or modifiers, and legal stratagems filtered to the current phase and selected unit. Because attacks are always resolved one unit at a time through the same attack pipeline, this layer should be front-and-center whenever an action begins. citeturn37search0turn36search2turn44view0turn44view3turn44view4

- **Battlefield-state layer.** This is spatial information that matters frequently but should appear on the board rather than in text panels: objective ownership, engagement and charge distances, aura or support radii, hidden or detection-range states, and the specific terrain areas that count as objectives. In 11th previews especially, terrain is no longer decorative bookkeeping; it is mechanically central to visibility, cover, and objective control. citeturn26view0turn26view1turn26view3turn26view5turn25view0

- **Planning layer.** This includes the roster strip, reserves, attached Leaders and Support units, transports, available detachments, and mission-hand planning. Players consult this often enough that it should be quickly reachable, but not so often that it deserves to permanently crowd the battlefield. citeturn27view1turn42view2turn42view3turn40view3

- **Deep inspection layer.** Full datasheet text, enhancement explanations, keywords, wargear options, faction rules, detachment rules, and edge-case FAQs are high-importance but lower-frequency. These belong in a dedicated inspector panel or popover, not in the default HUD. This is exactly the kind of complexity that progressive disclosure is designed to manage. citeturn35view0turn35view2turn43view0

A useful shorthand is this: **if a player uses it to make a decision in the next 3–10 seconds, it belongs in the glance or activation layers; if they use it to verify or resolve a question, it belongs in planning or deep inspection.** That split matches both the game’s rules cadence and UX best practice for complex applications. citeturn35view2turn35view3turn35view4

## Ergonomic display recommendations

The most important ergonomic choice is to give different data classes different **presentation grammars**. Scalar status belongs in small always-on counters; cards belong in card-like containers; spatial rules belong on the battlefield as overlays; and dense rule text belongs in an inspector. Nielsen Norman Group’s guidance on visual hierarchy, predictable placement, proximity, and common region strongly supports this kind of separation, because it helps users infer what is related, what is currently important, and what deserves attention first. citeturn35view1turn35view2turn35view5turn35view6

For the **always-visible game state**, use a narrow top strip. This is where the timer, round, phase, active player, score, and CP should live. Keep it visually stable from game start to game end. If you include a game timer, treat it as quiet operational telemetry: always present, but only visually assertive when a threshold is crossed. This is the clearest application of the “dashboard” model: critical information, minimum interaction, immediate readability. citeturn35view3

For **mission information**, preserve the card metaphor instead of flattening everything into abstract labels. In 10th and 11th alike, missions are literally packaged as primary and secondary cards, and in 11th the player may be holding unscored secondaries over multiple turns. A small “hand” display near the top corners works well: one area for your current primary/secondary state, another mirrored area for the opponent. In 11th especially, because players can have asymmetric primaries, the HUD should present **both players’ mission identities simultaneously**, not bury the opponent’s primary in a submenu. citeturn40view3turn41view0turn41view2turn41view4

For the **army list**, your instinct about a rolodex is good. A side-mounted vertical rolodex or “card rail” is a strong fit because it honors how datasheets are actually consumed: players care first about the unit’s identity, then second about inspecting one card in depth. Give each unit a persistent tab showing name, wounds/models remaining, keywords or badges, and maybe a tiny readiness icon for moved/shot/fought. Selecting a tab should pull that card into a larger inspector without losing the rest of the rail. This approach also aligns with recognition-over-recall: the user recognizes the unit and its state from persistent tabs instead of remembering where it lives in a long list. citeturn43view0turn35view4turn35view8

For **full datasheet inspection**, use a right-side inspector panel with two densities. The collapsed state should show a condensed unit summary: defensive stats, OC, movement, main weapons, key abilities, and attached Leader/Support status. The expanded state should show the full rules text, weapon list, keywords, enhancements, and rare clauses. That is textbook progressive disclosure: frequent facts first, deep text second. In your example of a rolodex, the selected card “resting on top” with full content visible is exactly the right interaction model. citeturn35view0turn35view2turn42view2turn31search0

For **stratagems**, do not show the whole catalogue all the time. The rules themselves show why: legality depends on phase, target, army construction, and timing windows. A much better approach is a context-sensitive stratagem tray that defaults to **eligible now**, with a toggle to “show all detachment/core.” This lowers cognitive load, reduces accidental misses, and matches the way players actually think in game states: “What can I do with this unit right now?” rather than “What are all 18 things in my codex?” citeturn37search0turn43view1turn44view0turn44view3turn44view4turn35view8

For **dice and attack resolution**, put a bottom-center “workbench” over the lower edge of the screen. The workbench should show the attack resolver as a compact pipeline: attacks → hits → wounds → saves → damage. It should also expose rerolls, critical triggers, modifier icons, and a short action log. This is the information players reference constantly, and it is inherently sequential, so presenting it as a horizontal pipeline is more ergonomic than dumping rolls into a floating text feed. Because the core rules define a repeatable attack sequence and many reroll windows, this workbench is arguably the single highest-value interaction zone after the battlefield itself. citeturn36search1turn36search2turn37search0

For **battlefield overlays**, reserve board space only for spatially meaningful information: move paths, charge ranges, objective control areas, hidden state, detection rings, and action radii. Do not put full rules text on the table itself. The 11th terrain previews especially justify this: objectives are often terrain areas, hidden models care about detection range, and movement/combat rules increasingly depend on where units sit in relation to terrain and engagement boundaries. Spatial facts should therefore be rendered spatially. citeturn26view0turn26view3turn26view5turn25view0

## HUD layout concepts

### Compass ring

This layout is best if you want the battlefield to remain visually dominant and the HUD to feel like an instrument cluster around it.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ Opponent missions   Score / CP / Round / Phase / Timer   Your missions  │
├───────────────┬──────────────────────────────────────────────┬──────────┤
│ Army rolodex  │                                              │ Inspector│
│ unit tabs     │              TABLETOP VIEWPORT               │ selected │
│ wounds/status │     overlays: move, charge, objectives,      │ card /   │
│ reserves tabs │         hidden, aura, detection range        │ target   │
│               │                                              │ compare  │
├───────────────┴──────────────────────────────────────────────┴──────────┤
│                 Action workbench / dice resolver / stratagem tray       │
└─────────────────────────────────────────────────────────────────────────┘
```

Why it works: the top edge becomes the stable operational strip; the left edge becomes the recognition-heavy roster rail; the right edge becomes the deep inspector; and the bottom edge becomes the phase-specific workbench. This keeps the center almost entirely for the tabletop, while still supporting a lot of density through fixed geography, visual grouping, and progressive disclosure. It is especially strong if you expect frequent unit selection and lots of direct attack resolution. citeturn35view1turn35view2turn35view5turn35view6turn35view3

The multi-use behavior is straightforward. The right inspector defaults to the selected unit; when an attack is declared, it temporarily becomes a **selected-vs-target comparison** panel; when no unit is selected, it can show recent rules lookups or the currently hovered mission card. The bottom workbench defaults to phase actions; during rolling, it becomes the dice/modifier pipeline; during the opponent’s turn, it emphasizes reactive stratagems and reaction windows. This gives you modal power without changing geography. citeturn44view0turn44view3turn44view4turn35view0

### Command bench

This layout is better if you want the UI to feel slightly more like a digital tabletop command station and you are willing to devote more space to planning and inspection.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ Compact top ribbon: active player · round · phase · timer · score       │
├───────────────┬──────────────────────────────────────────────┬──────────┤
│ Player bench  │                                              │ Opponent │
│ roster cards  │              TABLETOP VIEWPORT               │ bench    │
│ CP / missions │      cleaner board, fewer permanent edge     │ missions │
│ reserves      │            overlays until interaction        │ roster   │
├─────────────────────────────────────────────────────────────────────────┤
│ Full-width command bench: selected unit · target · weapons ·            │
│ stratagems · dice pipeline · combat math · action history               │
└─────────────────────────────────────────────────────────────────────────┘
```

Why it works: this version makes the **bottom bench** the main control surface and leaves the battlefield cleaner when nothing is happening. It is strongest for players who want richer attack planning, target comparison, and filtered options in one place. It also works well for spectators or stream viewers because the bottom panel can summarize what is happening without forcing the eye to bounce between many side panels. citeturn35view3turn35view1turn35view7

The tradeoff is that the bottom bench becomes more important, so it must be extremely disciplined. It should show only one principal mode at a time: movement planning, shooting resolution, charge resolution, or fight resolution. If you choose this layout, I would still keep the rolodex idea inside the left bench, but make the selected card “dock” into the command bench once chosen. That gives you the tactility of datacards without sacrificing the large, readable attack workspace that 40k’s dice-heavy interactions benefit from. citeturn36search2turn37search0turn35view0turn35view2

## Interface design rules

- **Keep the battlefield sacred.** Anything that is not spatial should migrate off the tabletop viewport. Board overlays should be reserved for movement, charge, visibility, objective, and terrain information. citeturn26view0turn26view3turn25view0

- **Give persistent information a permanent home.** Turn, phase, timer, score, and CP should never migrate between panels. Predictable placement is one of the simplest ways to manage visual complexity. citeturn35view2turn35view3

- **Design for recognition, not recall.** Show unit identity, state, and current options directly in the interface. Players should not have to remember which unit still has an enhancement, which stratagem is reactive, or what a tab refers to. citeturn35view4turn35view8

- **Use progressive disclosure aggressively.** Show condensed stats by default, then allow expansion into full datasheet text, FAQ language, and edge-case abilities only when requested. citeturn35view0turn35view2

- **Filter options by legality and timing.** Stratagems and reactions should default to “available now for this unit in this phase,” because the real cognitive load in 40k is not remembering that a rule exists; it is determining whether it is legal at this moment. citeturn37search0turn44view0turn44view3turn44view4

- **Represent each data type in the form it naturally takes.** Counters for scalar resources, cards for missions, overlays for space, and an inspector for text-heavy rules. Mixed metaphors create friction. citeturn35view1turn35view3turn40view3turn41view0

- **Use grouping and containment deliberately.** Mission information, score/counters, and unit actions should each live in clearly bounded regions so the eye can parse the HUD in chunks. citeturn35view5turn35view6

- **Make frequent controls big and labeled.** If a control matters every turn or every activation, it should be easy to acquire. Large labeled targets beat unlabeled icon-only controls for both speed and error reduction. citeturn35view7

- **Show the attack sequence as a pipeline, not a log.** Hit, wound, save, and damage are sequential cognitive steps, so the interface should mirror that sequence. citeturn36search1turn36search2

- **Version the rules model under the hood.** The UI should not hard-code 10th or 11th assumptions into layout. Stable classes should be constant while rule modules change beneath them. That is the cleanest way to survive balance updates, codex releases, and edition transitions. citeturn24view0turn42view0turn41view0

## Open questions and limitations

The main open issue is not the information architecture; it is **final 11th-edition enforcement detail**. At the time of the cited materials, the new core rules were newly released, faction packs were still rolling out, and the 11th Event Companion was described as still forthcoming. That means details like final organized-play conventions, exact faction breadth, and some edge-case timing standards may still settle. The recommendations above are therefore intentionally aimed at the stable information classes that both 10th and 11th share, while leaving exact rules implementation versionable. citeturn24view0turn41view0turn14search6

navlistRecent coverage of the 11th edition transitionturn39news14,turn38news16
