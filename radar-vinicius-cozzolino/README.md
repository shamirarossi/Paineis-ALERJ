# Radar do Diário Oficial · Vinicius Cozzolino

Leitura diária da **Parte II (Poder Legislativo)** do Diário Oficial do Estado do Rio de Janeiro para o gabinete do deputado estadual Vinicius Cozzolino.

Endereço do painel: `https://shamirarossi.github.io/Paineis-ALERJ/radar-vinicius-cozzolino/`

O painel destaca:

- **Magé:** qualquer ato que mencione o município ou seus distritos (Santo Aleixo, Suruí, Guia de Pacobaíba, Mauá, Inhomirim, Piabetá, Vila Inhomirim);
- **TEA e mães atípicas;**
- **Segurança pública** em todo o estado;
- **Baixada Fluminense:** os outros municípios da região;
- **Do gabinete:** projetos, emendas, relatorias e citações do deputado;
- **Nomeações e exonerações** da ALERJ.

## Como funciona

O painel usa o mesmo robô do [Radar do Diário Oficial (ALERJ)](../radar-do-alerj/). Todo dia útil de manhã, o Claude lê a edição **uma única vez** e separa o que importa para cada gabinete, com temas, notas e resumo próprios. A leitura completa fica em `../leituras/`, e este painel recebe só a parte dele em `data/`.

- Os temas e os critérios ficam no perfil `"vc"` em `../radar-do-alerj/scripts/ler_do.py` (variável `PERFIS`).
- Os nomes e as cores das abas ficam no bloco `window.PERFIL`, no `index.html` desta pasta.

Os resumos são gerados automaticamente. Antes de citar, confira sempre o texto original pelo link "Abrir o Diário Oficial".
