# Diagram of support from Combined AI + UI

- Green: implemented in core and the current UI has explicit usable workflow.
- Orange: implemented in core/adapter contracts, but current UI lacks semantic tooling.
- Grey: not currently present as a player-facing core DecisionRequest, or not implemented as an interactive flow.

```mermaid
flowchart TD
  classDef green fill:#2e7d32,stroke:#1b5e20,color:#ffffff;
  classDef orange fill:#c47f3a,stroke:#7a4818,color:#111111;
  classDef grey fill:#777777,stroke:#444444,color:#ffffff;

  Start["Start local game session"]:::green

  Start --> ArmyUI["Army/roster mustering as player DecisionRequest"]:::grey
  ArmyUI --> MusterConfig["Muster armies from GameConfig army_muster_requests"]:::orange

  MusterConfig --> MissionPrompt["Player mission/layout selection prompt"]:::grey
  MissionPrompt --> MissionConfig["MissionSetup, attacker/defender, turn_order supplied by config"]:::orange
  MissionConfig --> Battlefield["Create battlefield + UI projection/rendering"]:::green

  Battlefield --> Secondary["select_secondary_missions"]:::orange
  Secondary --> Reserves["select_reserve_declaration"]:::orange
  Reserves --> DeploySelect["select_deployment_unit"]:::orange
  DeploySelect --> DeployPlace["submit_deployment_placement"]:::orange
  DeployPlace --> Redeploy["select_redeploy_unit -> submit_redeploy_placement"]:::orange
  Redeploy --> Scout["select_prebattle_action -> submit_scout_move / submit_scout_reserve_setup"]:::orange
  Scout --> FirstTurnPrompt["Determine first turn as player-facing prompt"]:::grey
  FirstTurnPrompt --> SetupGate["Setup completion gate / enter battle"]:::orange

  SetupGate --> Command["Command phase: CP, tactical cards, battle-shock, mission hooks"]:::orange
  Command --> Tactical["draw/replace/discard/score tactical secondaries"]:::orange
  Command --> CommandStrats["Command-phase stratagem windows / target binding"]:::orange
  Command --> Dice["Dice roll display + finite reroll requests"]:::green

  Tactical --> MovementSelect["select_movement_unit"]:::green
  MovementSelect --> MovementAction["select_movement_action"]:::green
  MovementAction --> MoveDraft["submit_movement_proposal: normal / advance / fall_back"]:::green
  MovementAction --> MovePlacement["select_reinforcement_unit / select_disembark_unit -> submit_placement_proposal"]:::orange
  MoveDraft --> MoveReactions["End/opponent movement reactions: Overwatch, Rapid Ingress, triggered movement"]:::orange
  MovePlacement --> MoveReactions

  MoveReactions --> ShootingSelect["select_shooting_unit"]:::orange
  ShootingSelect --> ShootingType["select_shooting_type"]:::orange
  ShootingType --> ShootingDecl["submit_shooting_declaration"]:::orange
  ShootingDecl --> RangedResolution["Resolve ranged attacks: target group, weapon group, allocation, Precision, FNP, destruction reactions"]:::orange

  RangedResolution --> ChargeSelect["select_charging_unit"]:::orange
  ChargeSelect --> ChargeRoll["Engine charge roll"]:::orange
  ChargeRoll --> ChargeMove["submit_movement_proposal: charge_move"]:::orange

  ChargeMove --> FightSelect["select_fight_activation"]:::orange
  FightSelect --> FightAbility["select_fight_activation_ability"]:::orange
  FightAbility --> PileIn["submit_movement_proposal: pile_in"]:::orange
  PileIn --> MeleeDecl["submit_melee_declaration"]:::orange
  MeleeDecl --> MeleeResolution["Resolve melee attacks: target group, weapon group, allocation, FNP, destruction reactions"]:::orange
  MeleeResolution --> Consolidate["submit_movement_proposal: consolidate"]:::orange
  Consolidate --> FightInterrupt["resolve_fight_interrupt / Counteroffensive"]:::orange

  FightInterrupt --> NextTurn["Advance phase / turn / battle round"]:::orange
  NextTurn --> Command
  ```
# Diagram of just AI core-engine

- Green: implemented in Warhammer_40k_AI and exposed through lifecycle/DecisionRequest/projection/event wiring.
- Dull orange: implemented in core domain/config/events, but not exposed as appropriate lifecycle DecisionRequests or UI-facing adapter contract yet.
- Grey: rule/mechanic exists conceptually but is not materially implemented in core.

```mermaid
flowchart TD
  classDef green fill:#2e7d32,stroke:#1b5e20,color:#ffffff;
  classDef orange fill:#c47f3a,stroke:#7a4818,color:#111111;
  classDef grey fill:#777777,stroke:#444444,color:#ffffff;

  Start["GameLifecycle.start(config)"]:::green

  Start --> Muster["Muster armies from GameConfig army_muster_requests"]:::orange
  Muster --> Mission["Mission / layout / terrain from GameConfig MissionSetup"]:::orange
  Mission --> AttackerDefender["Determine attacker / defender"]:::orange
  AttackerDefender --> Battlefield["Create battlefield from MissionSetup"]:::green
  Battlefield --> Secondaries["select_secondary_missions"]:::green
  Secondaries --> Formations["select_reserve_declaration"]:::green
  Formations --> Deployment["select_deployment_unit"]:::green
  Deployment --> DeploymentPlacement["submit_deployment_placement"]:::green
  DeploymentPlacement --> Redeploy["select_redeploy_unit"]:::green
  Redeploy --> RedeployPlacement["submit_redeploy_placement"]:::green
  RedeployPlacement --> Prebattle["select_prebattle_action"]:::green
  Prebattle --> ScoutReserve["submit_scout_reserve_setup"]:::green
  Prebattle --> ScoutMove["submit_scout_move"]:::green
  ScoutReserve --> FirstTurn["Determine first turn"]:::orange
  ScoutMove --> FirstTurn
  FirstTurn --> SetupGate["Setup completion gate / enter battle"]:::green

  SetupGate --> Command["Command phase handler"]:::green
  Command --> TacticalDraw["draw_tactical_secondary_missions"]:::green
  Command --> TacticalReplace["replace_tactical_secondary_mission"]:::green
  Command --> BattleShock["Battle-shock step"]:::orange
  Command --> CommandStrat["Command-phase stratagem windows"]:::green

  TacticalDraw --> Movement["Movement phase handler"]:::green
  TacticalReplace --> Movement
  BattleShock --> Movement
  CommandStrat --> Movement

  Movement --> MoveUnit["select_movement_unit"]:::green
  MoveUnit --> MoveAction["select_movement_action"]:::green
  MoveAction --> NormalMove["submit_movement_proposal: normal_move"]:::green
  MoveAction --> Advance["Advance roll -> submit_movement_proposal: advance"]:::green
  MoveAction --> FallBack["submit_movement_proposal: fall_back"]:::green
  MoveAction --> RemainStationary["remain_stationary finite resolution"]:::green
  Movement --> Disembark["select_disembark_unit"]:::green
  Disembark --> DisembarkPlace["submit_placement_proposal: disembark placement"]:::green
  Movement --> Reinforce["select_reinforcement_unit"]:::green
  Reinforce --> ReinforcePlace["submit_placement_proposal: reserves / deep strike / ingress"]:::green
  Movement --> Embark["select_embark_transport"]:::green
  Movement --> DesperateEscape["select_desperate_escape_model"]:::green

  NormalMove --> MovementReactions["End/opponent movement reactions"]:::green
  Advance --> MovementReactions
  FallBack --> MovementReactions
  DisembarkPlace --> MovementReactions
  ReinforcePlace --> MovementReactions

  MovementReactions --> RapidIngress["submit_stratagem_target_proposal: Rapid Ingress"]:::green
  RapidIngress --> RapidIngressPlace["submit_placement_proposal: Rapid Ingress placement"]:::green
  MovementReactions --> FireOverwatch["submit_stratagem_target_proposal: Fire Overwatch"]:::green
  FireOverwatch --> OverwatchShoot["submit_shooting_declaration: forced snap shooting"]:::green

  MovementReactions --> Shooting["Shooting phase handler"]:::green
  Shooting --> ShootUnit["select_shooting_unit"]:::green
  ShootUnit --> ShootType["select_shooting_type"]:::green
  ShootType --> ShootDecl["submit_shooting_declaration"]:::green
  ShootDecl --> RangedTargets["select_resolve_target_unit"]:::green
  RangedTargets --> RangedWeaponGroup["select_attack_weapon_group"]:::green
  RangedWeaponGroup --> Precision["select_precision_allocation"]:::green
  Precision --> AllocationOrder["select_allocation_order"]:::green
  AllocationOrder --> DamageModel["select_damage_allocation_model"]:::green
  DamageModel --> FeelNoPain["select_feel_no_pain"]:::green
  FeelNoPain --> DestructionReaction["select_destruction_reaction"]:::green
  DestructionReaction --> Healing["select_healing_model"]:::green

  Healing --> Charge["Charge phase handler"]:::green
  Charge --> ChargeUnit["select_charging_unit"]:::green
  ChargeUnit --> ChargeRoll["Engine charge roll"]:::green
  ChargeRoll --> ChargeMove["submit_movement_proposal: charge_move"]:::green
  ChargeMove --> ChargeStrats["Charge-phase stratagem target proposals"]:::green

  ChargeStrats --> Fight["Fight phase handler"]:::green
  Fight --> FightActivation["select_fight_activation"]:::green
  FightActivation --> FightAbility["select_fight_activation_ability"]:::green
  FightAbility --> PileIn["submit_movement_proposal: pile_in"]:::green
  PileIn --> MeleeDecl["submit_melee_declaration"]:::green
  MeleeDecl --> MeleeTargets["select_resolve_target_unit"]:::green
  MeleeTargets --> MeleeWeaponGroup["select_attack_weapon_group"]:::green
  MeleeWeaponGroup --> MeleeAl
```