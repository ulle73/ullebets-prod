# Alla modeller: skuggjournal och jämförelse

## Syfte

Systemet ska vid varje giltig oddssnapshot beräkna och arkivera EV från varje aktiv, reproducerbar JS-formel samt varje fryst ML-modellartefakt. Varje positiv, prematch och domängiltig observation ska räknas som ett virtuellt skuggspel på 1u. Efter match ska samma observation rättas och kompletteras med closing line value (CLV), så att modell/formel, statkey, scope, period, riktning, liga och checkpoint kan jämföras över tid.

## Produktkontrakt

- Den befintliga förregistrerade forward-journalen är fortsatt enda källa för verkliga Auto-val. Skuggjournalen får aldrig skapa eller ändra `forward_bets`.
- Skuggjournalen sparar alla numeriska EV-resultat, även EV som inte är positivt, så att kalibrering kan studeras utan urvalsbias.
- `shadow_stake_units` är `1.0` endast när EV är större än noll, oddset är giltigt, snapshoten är prematch och källan är giltig för jämförelse. I övriga fall är insatsen `0.0` och orsaken sparas.
- Ett virtuellt spel identifieras av formel/modell, exakt snapshot, marknadssida och versionsfingeravtryck. En redan sparad observation är oföränderlig; en avvikande replay ska hårdfela.
- Flera checkpoints för samma lina sparas separat. API och UI får gruppera dem pedagogiskt, men råobservationerna får inte slås ihop eller skrivas över.
- “Alla formler” avser de numeriska EV-nycklar som den versionslåsta V2 JS-runtimen faktiskt emitterar och de frysta V2–V6-artefakter som finns i ett explicit register. Förkastade historiska experiment ingår inte.
- ML-rader utanför träningsdomänen sparas för revision men får ingen virtuell insats och får inte ingå i ROI/CLV-rankningen.
- Gamla MongoDB-databaser är read-only källor. Alla nya writes ska hårdfela om `MONGODB_DB` inte är exakt `ullebets_v2`.

## Datamodell

### `formula_observations`

En oföränderlig rad per källformula och marknadssida. Minsta kontrakt:

- identitet: `observation_key`, `observation_fingerprint_sha256`, `source_score_key`
- källa: `formula_id`, `formula_label`, `formula_family`, `formula_version`, `source_type`
- match: `match_key`, `league_key`, `league_name`, `home_team_name`, `away_team_name`, `match_start_time`
- marknad: `snapshot_key`, `snapshot_label`, `snapshot_type`, `odds_snapshot_time`, `stat_key`, `scope`, `period`, `direction`, `line_value`, `offered_odds`
- score: `predicted_win_probability`, `expected_roi_units`, `expected_ev_pct`, `domain_status`, `valid_for_comparison`, `is_positive_ev`, `shadow_stake_units`, `exclusion_reason`
- proveniens: `model_id`, `artifact_sha256` för ML eller `runtime_sha256` för JS

### `formula_results`

En rebuildbar rad per observation. Den kopierar rapporteringsdimensionerna och innehåller `settlement_status`, `settlement_result`, `actual_value`, `pnl_units`, `clv_status`, `official_clv`, `clv_pct`, `beat_closing_line`, `refreshed_at`. Rättningen använder befintlig gemensam settlement- och CLV-logik.

## Jämförelsemått

API:t ska som standard mäta endast domängiltiga +EV-skuggspel. Det ska returnera både antal observationer och unika matcher eftersom observationer från samma match är korrelerade.

- volym: observationer, virtuella spel, rättade spel, unika matcher
- utfall: vunna, förlorade, push, insats, P/L och ROI
- sannolikhetskvalitet: Brier score och log loss för binära, rättade utfall med giltig sannolikhet
- marknadskvalitet: officiell CLV-täckning, genomsnittlig CLV och andel som slår closing
- underlagsnivå: `early` under 30 rättade eller 15 matcher, `growing` från 30/15, `comparable` från 300/150

Ingen sortering eller text får kalla en formel “bevisad” enbart på historisk ROI eller litet forward-underlag.

## UI

`/modell` ska få en primär vy “Modelljämförelse” med:

1. fyra lättlästa sammanfattningsrutor för virtuella +EV-spel, rättade, P/L/ROI och officiell CLV,
2. filter för formel, familj, statkey, scope, period, riktning, liga och checkpoint,
3. en jämförelsetabell med formel, underlag, ROI, CLV och kalibrering,
4. tydliga underlagsbadges och en kort förklaring att flera observationer kan komma från samma match,
5. befintlig runtime/proof-status kvar som sekundär sektion.

Filter ska ligga i URL-parametrar, vara tillgängliga med labels och fungera på smala skärmar utan horisontell sidscroll.

## Automation och återhämtning

- Efter varje checkpoint- eller closing-hämtning körs samtliga registrerade frysta modeller och materialisering av JS-formler/ML-scorer.
- Efter postmatch enrichment körs en idempotent refresh av `formula_results`.
- Orkestreringen är registerstyrd och hårdfelar om en registrerad artefakt eller manifest saknas eller om en delkörning misslyckas.
- En manuell recovery-körning ska kunna materialisera saknade observationer och resultat utan att ändra existerande immutable rader.

## Acceptans

- En replay av samma inputs ger endast `existing`; ändrade immutable data ger konflikt.
- Samma marknadssida vid T-3D och T-2H ger två observationer och kan filtreras var för sig.
- En +EV-rad rättas till win/loss/push med korrekt 1u-P/L och får CLV när closing finns.
- En out-of-domain-rad syns i revisionsvolym men påverkar inte ROI.
- Read API kan filtrera och summera utan att blanda in `forward_bets`.
- Frontend visar tomt, laddning, fel, litet underlag och filtrerad data utan påhittade reservvärden.
