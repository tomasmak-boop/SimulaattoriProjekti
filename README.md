# CIP-simulaatioalusta

Monisessiollinen OPC UA -yhdyskäytävä ja ohjauspaneeli prosessisimulaatioille.
Yksi vakaa OPC UA -päätepiste, monta rinnakkaista simulaatioistuntoa –
CODESYS näkee jokaisen istunnon omana kansionaan.

Tämä haara sisältää **P3-runtime-kovennukset** sekä aiemmin tehdyt
**P4-kuormitustestin työkalut ja plugin-ohjeen**.

## Pika-aloitus kehitysympäristössä

### Ubuntu / WSL

Siirry projektin juurihakemistoon ja aktivoi Python-virtuaaliympäristö:

```bash
cd /polku/projektiin/SimulaattoriProjekti
source .venv/bin/activate
```

Asenna tietokantamuutokset ja suorita tarkistukset:

```bash
python manage.py migrate
python manage.py check
python -m pytest tests/unit -q
python manage.py test -v 1
```

Käynnistä Redis erikseen, jos se ei ole jo käynnissä. Tarkista tila ja
käynnistä sovellus:

```bash
redis-cli ping
bash scripts/stack.sh up --slug p3check
```

Kun Redis toimii, sen vastauksen tulee olla `PONG`. Stack-komento käynnistää
palvelut ja luo testisimulaatioistunnon. Tarkista palveluiden tila:

```bash
bash scripts/stack.sh status
```

Sammuta kehitysympäristön palvelut:

```bash
bash scripts/stack.sh down
```

## Istunnon ja slug-uudelleenkäytön testaus

Listaa Gatewayn näkemät istunnot:

```bash
bash scripts/stack.sh cli --list-sessions
```

Luo uusi istunto:

```bash
bash scripts/stack.sh create --slug p3check "P3 testi"
```

Luo toinen istunto samalla slugilla palveluita sammuttamatta:

```bash
bash scripts/stack.sh create --slug p3check "Slug-uudelleenkäytön testi"
```

Uuden istunnon pitäisi käynnistyä ilman Gatewayn uudelleenkäynnistystä.
Tämä testaa korjauksen, joka poistaa vanhan istuntokansion OPC UA -puusta.

## Arkkitehtuuri lyhyesti

```text
CODESYS / SCADA ──▶ OPC UA Gateway :8080 ──▶ Worker-prosessit :5xxx
                          ▲                         │
                          │                    HTTP :6xxx
Selain / REST ──▶ Django Control Plane :8000       │
                          │                         │
                          └────── Redis Streams ◀───┘
```

- **Django-ohjauspaneeli (:8000)** – selainkäyttöliittymä ja REST-rajapinta
- **OPC UA Gateway (:8080)** – yksi päätepiste kaikkien istuntojen arvoille
- **Worker Pool Daemon** – käynnistää, pysäyttää ja valvoo työntekijöitä
- **Worker-prosessit (:5xxx)** – ajavat yksittäisiä simulaatioita; niiden
  HTTP-näkymät käyttävät porttialuetta `:6xxx`
- **Redis Streams** – komentoväylä, tapahtumat, heartbeatit ja porttivaraukset

## P3-muutokset tässä haarassa

- Enintään **100 aktiivista istuntoa**; rajan täyttyessä API palauttaa HTTP
  503 -vastauksen.
- Enintään **10 istunnonluontipyyntöä/IP/minuutti**. Redis-häiriössä
  rajoitin kirjaa varoituksen ja sallii pyynnön.
- Gateway poistaa irrotetun istunnon kansiorakenteen, jotta slug voidaan
  käyttää uudelleen.
- Gateway tunnistaa myös vanhan heartbeat-muodon palvelimen
  uudelleenkäynnistyksen jälkeen.
- Idle-timeout huomioi OPC UA -liikenteen ja dashboardin HTTP-pyynnöt.
- Per-istunto OPC UA -käyttäjätunnukset ovat valinnainen tila:
  `OPCUA_AUTH_MODE=per_session`. Oletus `none` säilyttää anonyymit yhteydet.
- Gatewayn uudelleenyhdistämisen viiveet ja näytteenottoväli ovat
  säädettävissä.

> **Tietoturvahuomio:** OPC UA käyttää tällä hetkellä `NoSecurity`-siirtotapaa.
> Käyttäjätunnus ja salasana eivät salaa verkkoliikennettä. Pidä yhteydet
> loopback-osoitteessa tai luotetussa verkossa.

## P4-kuormitustesti ja plugin-ohje

- [Pluginin tekijän opas](docs/plugin-guide.md)
- [Kuormitustestin ja luovutuksen ohje](docs/handover.md)

Kuormitustesti on valinnainen, eikä tälle haaralle ole vielä vahvistettua
tuotantoympäristön skaalautuvuusarviota. Noudata handover-ohjetta ja varmista
siivous ennen suurempia testejä:

```bash
LOAD_TESTS_ENABLED=1 python -m pytest tests/load/test_n_sessions.py -q
```

## Hakemistorakenne

```text
control_plane/       Django-ohjauspaneeli ja REST-rajapinta
gateway/             OPC UA -yhdyskäytävä
worker_pool/         Työntekijäprosessien hallinta
sim_runtime/         Simulaatioajonaika sekä OPC UA- ja HTTP-adapterit
sim_plugins/         Simulaatiopluginit (cip, blinker, loadtest)
tests/               Yksikkö-, manuaali- ja kuormitustestit
tools/               Kehitys- ja kuormitustestityökalut
docs/                Plugin-opas ja kuormitustestin luovutusohje
scripts/stack.sh     Paikallisen kehityspinon käynnistys ja hallinta
```

## Vaatimukset

- Ubuntu/WSL tai muu tuettu Linux-kehitysympäristö
- Projektin Python-riippuvuudet ja virtuaaliympäristö `.venv`
- Redis
- OPC UA -asiakas kuormitus- ja yhteystesteihin

## Testauskomennot

```bash
python manage.py migrate
python manage.py check
python -m pytest tests/unit -q
python manage.py test -v 1
python manage.py makemigrations --check --dry-run
```

Projektin taustamateriaali: [project_dump](https://github.com/laksuni/misc/tree/main/project_dump)
(päivitetty 21.10.2026).
