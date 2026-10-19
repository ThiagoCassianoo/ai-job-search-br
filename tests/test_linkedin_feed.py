"""Tests for tools/linkedin_feed.py - the daily LinkedIn collector's hard filters.

LinkedIn's "remote" filter let on-site jobs in other cities through in the
first real run, so the workplace type is read from the description. These pin
that reading and the rules built on it: what is dropped before scoring
(on-site/hybrid outside Espírito Santo), what is only flagged (English above
basic), and the title/dedupe rules that keep the feed short.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from linkedin_feed import (  # noqa: E402
    dedupe_key, detect_modality, excluded_title, hard_filter, in_es, requires_english,
)


class Modality(unittest.TestCase):
    def test_remote(self):
        self.assertEqual(detect_modality("Vaga 100% remota para todo o Brasil."), "remoto")
        self.assertEqual(detect_modality("Trabalho remoto, horário flexível."), "remoto")

    def test_remote_synonyms_seen_in_real_postings(self):
        self.assertEqual(detect_modality("Turno: 08:00-17:40  Modalidade: Teletrabalho"), "remoto")
        self.assertEqual(detect_modality("Disponibilidade para home-office"), "remoto")

    def test_onsite(self):
        self.assertEqual(detect_modality("Formato: CLT | presencial de segunda a sexta"), "presencial")

    def test_hybrid(self):
        self.assertEqual(detect_modality("Modelo híbrido, 3x por semana no escritório."), "hibrido")

    def test_conflicting_wording_stays_undecided(self):
        self.assertEqual(detect_modality("Remoto, com encontros presenciais mensais em SP."), "indefinido")

    def test_silent_posting_is_undecided(self):
        self.assertEqual(detect_modality("Analisar dados e criar dashboards."), "indefinido")


class HardFilter(unittest.TestCase):
    def test_onsite_outside_es_is_dropped(self):
        keep, modality, _ = hard_filter("Curitiba, Paraná, Brazil", "CLT | presencial de segunda a sexta")
        self.assertFalse(keep)
        self.assertEqual(modality, "presencial")

    def test_hybrid_in_es_is_kept(self):
        keep, _, _ = hard_filter("Vitória, Espírito Santo, Brazil", "Modelo híbrido em Vitória.")
        self.assertTrue(keep)

    def test_remote_anywhere_is_kept(self):
        keep, _, _ = hard_filter("Salvador, Bahia, Brazil", "Vaga 100% remota.")
        self.assertTrue(keep)

    def test_senior_level_in_body_is_dropped(self):
        keep, _, _ = hard_filter("São Paulo, São Paulo, Brazil", "Nível: Sênior  Jornada: Segunda a Sexta. Home-office.")
        self.assertFalse(keep)

    def test_undecided_is_kept_for_the_scorer(self):
        keep, _, _ = hard_filter("São Paulo, São Paulo, Brazil", "Analisar dados com SQL.")
        self.assertTrue(keep)


class English(unittest.TestCase):
    def test_portuguese_requirement(self):
        self.assertTrue(requires_english("Requisitos: SQL, Python. Inglês intermediário/avançado."))
        self.assertTrue(requires_english("Inglês fluente é obrigatório."))

    def test_english_requirement(self):
        self.assertTrue(requires_english("What We're Looking For: Advanced English. SQL & Excel."))

    def test_posting_written_in_english(self):
        text = ("We are looking for a data analyst. You will work with the team and our stakeholders "
                "and you will build dashboards for the business with SQL. We are a team that values "
                "experience and you will have the chance to grow with us and with the product, and the "
                "role is for you if you like data and you are curious.")
        self.assertTrue(requires_english(text))

    def test_basic_or_absent_english_passes(self):
        self.assertFalse(requires_english("Desejável inglês básico para leitura de documentação."))
        self.assertFalse(requires_english("Experiência com Power BI e SQL para criar dashboards de dados."))


class Titles(unittest.TestCase):
    def test_senior_and_intern_titles_are_excluded(self):
        for t in ["Analista de Dados Sênior", "Data Engineer Sr.", "Estagiário de Dados", "Head of Data", "Trainee BI"]:
            self.assertTrue(excluded_title(t), t)

    def test_junior_and_mid_titles_pass(self):
        for t in ["Analista de Dados Jr", "Analista de BI Pleno", "Data Analyst"]:
            self.assertFalse(excluded_title(t), t)

    def test_same_posting_in_two_cities_shares_a_key(self):
        a = {"title": "Talent Data Analyst - Remote", "company": "INDI Staffing Services"}
        b = {"title": "talent data analyst - remote ", "company": "INDI Staffing Services"}
        self.assertEqual(dedupe_key(a), dedupe_key(b))

    def test_es_location(self):
        self.assertTrue(in_es("Serra, Espírito Santo, Brazil"))
        self.assertFalse(in_es("Osasco, São Paulo, Brazil"))


if __name__ == "__main__":
    unittest.main()
