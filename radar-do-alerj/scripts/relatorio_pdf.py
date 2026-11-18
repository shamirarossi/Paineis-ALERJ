#!/usr/bin/env python3
"""Relatório diário em PDF do Radar do Diário Oficial (painel da Dani Balbi).

Para cada edição em radar-do-alerj/data/edicoes/, monta uma página HTML com o resumo do dia,
os destaques do gabinete, os demais atos e os atos de pessoal, e a imprime em PDF com o
Google Chrome (headless). Os PDFs ficam em radar-do-alerj/relatorios/AAAA-MM-DD.pdf, e o
botão "Baixar relatório (PDF)" do painel aponta para eles.

Só refaz o PDF de uma edição quando ela foi lida de novo ou quando o modelo do relatório muda
(VERSAO), por isso pode rodar em toda execução do robô sem gerar publicações à toa.

Uso:
    python radar-do-alerj/scripts/relatorio_pdf.py              # gera os que faltam
    python radar-do-alerj/scripts/relatorio_pdf.py --todos      # refaz todos
    python radar-do-alerj/scripts/relatorio_pdf.py --html-apenas 2026-11-18   # só o HTML, para revisar
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent          # radar-do-alerj/
EDICOES = PASTA / "data" / "edicoes"
SAIDA = PASTA / "relatorios"
FONTES = PASTA / "relatorio" / "fontes"
MANIFESTO = SAIDA / "manifesto.json"
VERSAO = 2   # aumente para refazer todos os PDFs depois de mudar o modelo

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]
SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
TEMAS = [  # mesma ordem e cores do painel
    ("gabinete", "Do gabinete", "#ffc200"),
    ("lgbt", "LGBTQIA+", "linear-gradient(90deg,#c00a0a,#ec6000,#ffc200,#068b0f,#1648b6,#590f93)"),
    ("mulheres", "Mulheres", "#bf0097"),
    ("ct", "Ciência e Tecnologia", "#1648b6"),
]
NOME_TEMA = {k: n for k, n, _ in TEMAS}
COR_TEMA = {k: c for k, _, c in TEMAS}
GRUPOS = ["Leis e vetos", "Projetos de lei", "Pareceres de comissão", "Reuniões e audiências",
          "Indicações e requerimentos", "Atos da Mesa", "Escola do Legislativo", "Outros"]
ACOES = [("nomeacao", "Nomeações", "Nomeação"), ("exoneracao", "Exonerações", "Exoneração"),
         ("designacao", "Designações", "Designação"), ("dispensa", "Dispensas", "Dispensa")]

e = lambda s: html.escape(str(s or ""), quote=True)


def data_longa(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{SEMANA[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def temas_do(it: dict) -> list[str]:
    t = [x for x in it.get("temas", []) if x in NOME_TEMA]
    if it.get("gabinete"):
        t.insert(0, "gabinete")
    return t


def logo_svg() -> str:
    """Reaproveita o logo (versão para fundo roxo) que já está embutido no painel."""
    painel = (PASTA / "index.html").read_text("utf-8")
    m = re.search(r'<svg class="logo".*?</svg>', painel, re.S)
    return m.group(0).replace('class="logo"', 'class="logo" width="150"') if m else ""


def chips(ts: list[str]) -> str:
    return "".join(f'<span class="chip"><i style="background:{COR_TEMA[t]}"></i>{e(NOME_TEMA[t])}</span>' for t in ts)


def item_destaque(it: dict) -> str:
    meta = []
    if it.get("autor"):
        meta.append(f"<b>Autoria:</b> {e(it['autor'])}")
    if it.get("situacao"):
        meta.append(f"<b>Situação:</b> {e(it['situacao'])}")
    ts = temas_do(it)
    return f"""<article class="dest" style="--faixa:{COR_TEMA[ts[0]]}">
  <div class="top"><span class="tipo">{e(it.get('tipo'))}</span>{f'<span class="ref">{e(it["ref"])}</span>' if it.get('ref') else ''}<span class="chips">{chips(ts)}</span></div>
  <p class="ementa">{e(it.get('ementa'))}</p>
  {f'<p class="meta">{" · ".join(meta)}</p>' if meta else ''}
  {f'<p class="nota"><b>Por que importa:</b> {e(it["nota"])}</p>' if it.get('nota') else ''}
</article>"""


def montar_html(ed: dict, eid: str) -> str:
    itens = ed.get("itens", [])
    dest = [it for it in itens if temas_do(it)]
    resto = [it for it in itens if not temas_do(it)]
    cont = {k: sum(1 for it in itens if k in temas_do(it)) for k, _, _ in TEMAS}
    atos = ed.get("atosPessoal", [])
    n_atos = {k: sum(1 for a in atos if a.get("acao") == k) for k, _, _ in ACOES}

    # demais atos, por grupo
    por_grupo: dict[str, list] = {}
    for it in resto:
        por_grupo.setdefault(it.get("grupo") if it.get("grupo") in GRUPOS else "Outros", []).append(it)
    demais = ""
    for g in GRUPOS:
        if g not in por_grupo:
            continue
        linhas = "".join(
            f"<li><b>{e(it.get('tipo'))}{(' · ' + e(it['ref'])) if it.get('ref') else ''}.</b> {e(it.get('ementa'))}"
            f"{(' <span class=muted>(' + e(it['autor']) + ')</span>') if it.get('autor') else ''}</li>"
            for it in por_grupo[g])
        demais += f'<h3>{e(g)}</h3><ul class="demais">{linhas}</ul>'

    # atos de pessoal
    pessoal = ""
    if atos:
        linhas = ""
        for k, _, rot in ACOES:
            for a in [x for x in atos if x.get("acao") == k]:
                cargo = e(a.get("cargo")) + (f" ({e(a['simbolo'])})" if a.get("simbolo") else "")
                extra = []
                if a.get("a_pedido"):
                    extra.append("a pedido")
                if a.get("vaga_de"):
                    extra.append(f"na vaga de {e(a['vaga_de'])}")
                linhas += (f'<tr class="{k}"><td><span class="acao {k}">{rot}</span></td><td><b>{e(a.get("nome"))}</b>'
                           f'{("<br><span class=muted>" + "; ".join(extra) + "</span>") if extra else ""}</td>'
                           f'<td>{cargo}</td><td>{e(a.get("lotacao"))}</td></tr>')
        resumo_p = " · ".join(f"{n_atos[k]} {pl.lower()}" for k, pl, _ in ACOES if n_atos[k])
        pessoal = f"""<section class="sec quebra-ok">
  <h2>Nomeações, exonerações e designações</h2>
  <p class="muted">{e(resumo_p)}</p>
  <table class="pes"><thead><tr><th>Ato</th><th>Nome</th><th>Cargo</th><th>Lotação</th></tr></thead><tbody>{linhas}</tbody></table>
</section>"""

    numeros = "".join(f'<div class="num"><i style="background:{COR_TEMA[k]}"></i><b>{cont[k]}</b><span>{e(n)}</span></div>'
                      for k, n, _ in TEMAS)
    try:
        lido = dt.datetime.fromisoformat(ed["lidoEm"]).astimezone(dt.timezone(dt.timedelta(hours=-3))).strftime("%d/%m/%Y às %H:%M")
    except (KeyError, TypeError, ValueError):
        lido = ""
    fontes = FONTES.resolve().as_uri()

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Radar do Diário Oficial · {e(data_longa(ed['data']))}</title>
<style>
@font-face {{ font-family: "SS3"; src: url("{fontes}/SourceSans3-Regular.ttf"); font-weight: 400; }}
@font-face {{ font-family: "SS3"; src: url("{fontes}/SourceSans3-SemiBold.ttf"); font-weight: 600; }}
@font-face {{ font-family: "SS3"; src: url("{fontes}/SourceSans3-Bold.ttf"); font-weight: 700; }}
@font-face {{ font-family: "SS3"; src: url("{fontes}/SourceSans3-Black.ttf"); font-weight: 900; }}
@page {{
  size: A4; margin: 14mm 14mm 16mm;
  @bottom-left {{ content: "Radar do Diário Oficial · Gabinete Dani Balbi · {e(ed['data'][8:10] + '/' + ed['data'][5:7] + '/' + ed['data'][:4])}"; font: 400 8pt "SS3", sans-serif; color: #6b6072; }}
  @bottom-right {{ content: "Página " counter(page) " de " counter(pages); font: 400 8pt "SS3", sans-serif; color: #6b6072; }}
}}
* {{ box-sizing: border-box; }}
html {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
body {{ margin: 0; font: 400 10pt/1.42 "SS3", "Source Sans 3", sans-serif; color: #16091e; }}
.muted {{ color: #6b6072; }}
header.capa {{ background: #590f93; color: #f9f6ef; border-radius: 6px; padding: 14px 18px 0; overflow: hidden; }}
.capa .linha {{ display: flex; align-items: center; gap: 18px; }}
.capa .logo {{ height: auto; flex: none; }}
.capa h1 {{ margin: 0; font-weight: 900; font-size: 22pt; line-height: 1; letter-spacing: -.01em; }}
.capa h1 em {{ font-style: normal; color: #ffc200; }}
.capa p {{ margin: 4px 0 0; font-size: 10pt; opacity: .9; }}
.capa .data {{ margin-top: 10px; font-weight: 700; font-size: 13pt; }}
.pride {{ display: flex; height: 5px; margin: 14px -18px 0; }}
.pride span {{ flex: 1; }}
.sec {{ margin-top: 16px; }}
h2 {{ font-weight: 900; font-size: 13.5pt; margin: 0 0 6px; color: #590f93; break-after: avoid; }}
h3 {{ font-weight: 700; font-size: 8.5pt; letter-spacing: .08em; text-transform: uppercase; color: #6b6072; margin: 12px 0 4px; break-after: avoid; }}
.resumo {{ font-size: 11pt; margin: 0; }}
.nums {{ display: flex; gap: 8px; margin-top: 10px; }}
.num {{ flex: 1; border: 1px solid #e4dde9; border-radius: 6px; padding: 6px 9px; display: flex; align-items: baseline; gap: 6px; }}
.num i, .chip i {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex: none; }}
.num b {{ font-weight: 900; font-size: 15pt; line-height: 1; }}
.num span {{ font-size: 8.5pt; color: #6b6072; }}
.dest {{ border: 1px solid #e4dde9; border-radius: 6px; padding: 8px 11px 8px 14px; margin-bottom: 7px; position: relative; break-inside: avoid; }}
.dest::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; border-radius: 6px 0 0 6px; background: var(--faixa); }}
.dest .top {{ display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: center; }}
.tipo {{ font-weight: 700; color: #590f93; font-size: 9pt; }}
.ref {{ color: #6b6072; font-size: 9pt; }}
.chips {{ margin-left: auto; display: flex; gap: 4px; }}
.chip {{ font-size: 7.5pt; font-weight: 600; background: #f1eaf6; border-radius: 99px; padding: 1px 7px 1px 5px; display: inline-flex; align-items: center; gap: 4px; }}
.ementa {{ margin: 3px 0 0; }}
.meta {{ margin: 3px 0 0; font-size: 8.5pt; color: #6b6072; }}
.meta b {{ color: #16091e; font-weight: 600; }}
.nota {{ margin: 5px 0 0; background: #f1eaf6; border-radius: 4px; padding: 4px 7px; font-size: 9pt; }}
ul.demais {{ margin: 0; padding-left: 14px; }}
ul.demais li {{ margin-bottom: 3px; break-inside: avoid; }}
table.pes {{ width: 100%; border-collapse: collapse; font-size: 8.5pt; }}
table.pes th {{ text-align: left; font-size: 7.5pt; letter-spacing: .06em; text-transform: uppercase; color: #6b6072; border-bottom: 1px solid #e4dde9; padding: 4px 6px; }}
table.pes td {{ border-bottom: 1px solid #efe9f3; padding: 4px 6px; vertical-align: top; }}
table.pes tr {{ break-inside: avoid; }}
.acao {{ font-size: 7pt; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; border-radius: 4px; padding: 1px 5px; white-space: nowrap; }}
.acao.nomeacao {{ background: #e3f3e3; color: #067a0e; }}
.acao.exoneracao {{ background: #fbe3f4; color: #bf0097; }}
.acao.designacao {{ background: #f1eaf6; color: #590f93; }}
.acao.dispensa {{ background: #f1eef3; color: #6b6072; }}
.fonte {{ margin: 8px 0 0; font-size: 8pt; color: #6b6072; }}
.fonte a {{ color: #590f93; }}
</style></head>
<body>
<header class="capa">
  <div class="linha">{logo_svg()}
    <div><h1>Radar do <em>Diário Oficial</em></h1><p>Parte II · Poder Legislativo · relatório diário para o gabinete</p></div>
  </div>
  <div class="data">{e(data_longa(ed['data'])[0].upper() + data_longa(ed['data'])[1:])}{(' · ' + e(ed['edicao'])) if ed.get('edicao') else ''}{' · Edição extra' if ed.get('extra') else ''}</div>
  <div class="pride"><span style="background:#c00a0a"></span><span style="background:#ec6000"></span><span style="background:#ffc200"></span><span style="background:#068b0f"></span><span style="background:#1648b6"></span><span style="background:#590f93"></span><span style="background:#63caea"></span><span style="background:#f277b4"></span></div>
</header>

<p class="fonte">Fonte: Diário Oficial do RJ, Parte II{(' · ' + e(ed['edicao'])) if ed.get('edicao') else ''} (<a href="{e(ed.get('link'))}">abrir o original</a>). Resumos e destaques gerados automaticamente com o Claude{(' em ' + e(lido)) if lido else ''}; confira o texto original antes de citar. Painel completo: <a href="https://shamirarossi.github.io/Paineis-ALERJ/radar-do-alerj/">shamirarossi.github.io/Paineis-ALERJ/radar-do-alerj</a></p>

<section class="sec">
  <h2>Resumo do dia</h2>
  <p class="resumo">{e(ed.get('resumo'))}</p>
  <div class="nums">{numeros}<div class="num"><b>{len(itens)}</b><span>atos no total</span></div></div>
</section>

<section class="sec">
  <h2>Destaques para o gabinete</h2>
  {''.join(item_destaque(it) for it in dest) if dest else '<p class="muted">Nenhum ato desta edição trata dos temas do gabinete.</p>'}
</section>

{f'<section class="sec"><h2>Demais atos do dia</h2>{demais}</section>' if demais else ''}

{pessoal}


</body></html>"""


def achar_chrome() -> str:
    for nome in (os.environ.get("CHROME"), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if nome and shutil.which(nome):
            return shutil.which(nome)
    raise RuntimeError("Google Chrome não encontrado para gerar o PDF")


def imprimir(html_txt: str, destino: Path) -> None:
    chrome = achar_chrome()
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "relatorio.html"
        f.write_text(html_txt, "utf-8")
        destino.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        "--allow-file-access-from-files", f"--print-to-pdf={destino}", f.as_uri()],
                       check=True, capture_output=True, timeout=180)
    if not destino.exists() or destino.stat().st_size < 2000:
        raise RuntimeError(f"o PDF de {destino.stem} não foi gerado")


def marcar_no_indice() -> None:
    """Marca no indice.json do painel quais edições têm relatório, para o botão aparecer."""
    p = PASTA / "data" / "indice.json"
    try:
        ix = json.loads(p.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return
    mudou = False
    for ed in ix.get("edicoes", []):
        tem = (SAIDA / f"{ed['id']}.pdf").exists()
        if bool(ed.get("relatorio")) != tem:
            mudou = True
            if tem:
                ed["relatorio"] = f"relatorios/{ed['id']}.pdf"
            else:
                ed.pop("relatorio", None)
    if mudou:
        p.write_text(json.dumps(ix, ensure_ascii=False, indent=1) + "\n", "utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--todos", action="store_true", help="refaz todos os PDFs")
    ap.add_argument("--html-apenas", metavar="AAAA-MM-DD", help="grava só o HTML desta edição em relatorios/, para revisar")
    a = ap.parse_args()

    if a.html_apenas:
        ed = json.loads((EDICOES / f"{a.html_apenas}.json").read_text("utf-8"))
        out = SAIDA / f"{a.html_apenas}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(montar_html(ed, a.html_apenas), "utf-8")
        print(out)
        return 0

    try:
        manif = json.loads(MANIFESTO.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        manif = {}
    falhas = 0
    for f in sorted(EDICOES.glob("*.json")):
        eid = f.stem
        ed = json.loads(f.read_text("utf-8"))
        chave = f"{VERSAO}|{ed.get('lidoEm')}"
        pdf = SAIDA / f"{eid}.pdf"
        if not a.todos and pdf.exists() and manif.get(eid) == chave:
            continue
        try:
            imprimir(montar_html(ed, eid), pdf)
            manif[eid] = chave
            print(f"Relatório gerado: {pdf.relative_to(PASTA)}")
        except Exception as ex:  # um PDF com problema não pode derrubar a leitura do dia
            falhas += 1
            print(f"Não consegui gerar o relatório de {eid}: {ex}", file=sys.stderr)
    SAIDA.mkdir(parents=True, exist_ok=True)
    MANIFESTO.write_text(json.dumps(manif, ensure_ascii=False, indent=1, sort_keys=True) + "\n", "utf-8")
    marcar_no_indice()
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
