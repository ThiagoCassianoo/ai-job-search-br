# Search Queries for Job Scraper

<!-- SETUP: Customize these queries based on your skills, target roles, and location -->

## Installed portal CLIs (primary for `/scrape`)

`/scrape` discovers every portal skill under `.agents/skills/*/SKILL.md` and runs its CLI first. Shipped country-agnostic CLIs include `linkedin-search` and `freehire-search`; Danish demos and any skill you add with `/add-portal` are included the same way. You do **not** need a matching `site:` line below for those CLIs to run.

The `site:` query templates in this file are the **WebSearch fallback** — for portals without a CLI, company career pages, or when a CLI fails.

**Language scope:** write every query category in every language listed in your CLAUDE.md Languages table (typically 1-2, sometimes more). A posting requiring a language you have *not* declared, as a job condition, is excluded before scoring; a posting requiring a *higher level* than you declared in a language you *do* work in is flagged for your own judgment, not excluded — see `04-job-evaluation.md`'s Language Gate, the single source of truth for this rule. Translate each category's keywords rather than machine-translating word-for-word (e.g. "Frontend Developer" -> "Desarrollador Frontend", not a literal word-for-word translation) if you work in more than one language.

## Search Sites

Primary:
- **linkedin.com/jobs** - via `linkedin-search` CLI (location: "Brazil" com filtro remoto; e "Serra, Espírito Santo, Brazil" / "Vitória, Espírito Santo, Brazil" para presencial/híbrido)
- **freehire.me** - via `freehire-search` CLI (agregador; usar para remoto Brasil)
- **gupy.io** - maior ATS do Brasil; ainda sem CLI (criar depois com `/add-portal`). Até lá, só fallback `site:`
- **vagas.com.br** / **br.indeed.com** - fallback `site:` (opcional)

Secondary (company career pages via Google):
- Direct Google searches with `site:` filters for known target companies

## Query Categories

Queries em **português** (idioma principal). Títulos em inglês aparecem porque muitas vagas brasileiras de dados usam o título em inglês ("Data Analyst", "Data Engineer"); o Language Gate filtra as que exigem inglês fluente. Combine com "remoto" ou com a cidade.

### Priority 1: Dados & IA (construir pipelines, análises e automações com IA)

Direção principal de carreira. Senioridade: Júnior ou Pleno.

```
"Analista de Dados" remoto Brasil
"Engenheiro de Dados" Júnior remoto
"Data Engineer" Júnior Brasil remoto
"Analista de BI" OR "Analista de Business Intelligence" remoto
"Desenvolvedor de IA" OR "Engenheiro de IA" Júnior remoto
"Analista de Automação" Python remoto
site:linkedin.com/jobs "Analista de Dados" Vitória Espírito Santo
site:gupy.io "Analista de Dados" remoto
site:gupy.io "Engenheiro de Dados" Júnior
```

### Priority 2: Dados em Indústria / SSMA (operação industrial + dados)

Nicho onde a combinação rara (~6 anos em operação industrial + dados) é vantagem.

```
"Analista de Dados" indústria Espírito Santo
"Analista de BI" Power BI Serra OR Vitória ES
"Analista de Riscos" Power BI Espírito Santo
"Analista de SSMA" Power BI OR dados Vitória ES
"Analista de Indicadores" Power BI Espírito Santo
site:gupy.io "Power BI" Vitória ES
```

### Priority 3: Sistemas & Processos (onde há mais experiência formal)

```
"Analista de Sistemas" Pleno remoto
"Analista de Processos" Vitória OR Serra ES
"Analista de Requisitos" remoto
"Analista de Melhoria Contínua" Espírito Santo
site:gupy.io "Analista de Processos" Vitória
```

### Priority 4: Rede ampla (Python / Power BI / Automação)

```
"Python" analista Júnior remoto Brasil
"Power BI" analista remoto
"Power Platform" OR "Power Automate" analista remoto
"Analytics Engineer" Júnior remoto Brasil
```

## Location Filter

Remoto no Brasil: **PASS** (desde que não exija mudança).

Presencial/híbrido - definido a partir de Serra/ES *(faixas assumidas; ajuste se quiser)*:
- **Ideal:** Serra
- **Aceitável:** Vitória, Vila Velha, Cariacica
- **Limítrofe:** Viana, Fundão, Guarapari (sinalizar - deslocamento longo)
- **Longe demais:** qualquer cidade fora da Grande Vitória sem opção remota (exige mudança = deal-breaker)

## Language Filter

Your working languages and levels are in CLAUDE.md's Languages table. When filtering scraped results, apply `04-job-evaluation.md`'s Language Gate: a posting requiring a language you haven't declared at all is excluded; a posting requiring a higher level than you declared in a language you do work in is not excluded, flag it clearly instead (see `job-scraper/SKILL.md`'s Step 3 "Quick Fit Assessment" for how the flag surfaces in `/scrape` output). Postings simply *written* in a language you don't work in, that don't require it on the job, are fine.

## Date Filter

Only include jobs posted within the last 14 days, or with an application deadline that has not yet passed. If a posting date cannot be determined, include it but flag as "date unknown".

## Adapting Queries

If the user specifies a focus area, select queries from the matching category and also generate 2-3 custom queries for that focus. For example:
- "/scrape [focus_area]" -> relevant category queries + custom focus-specific queries
