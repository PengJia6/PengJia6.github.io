---
permalink: /
title: "About me"
author_profile: true
redirect_from:
  - /about/
  - /about.html
---

I am Peng Jia (贾鹏), a researcher at the First Affiliated Hospital of Xi'an Jiaotong University, China. My work focuses on computational methods for genome analysis, with interests in microsatellite instability, long-read sequencing, genome assembly, and variant benchmarking.

## Research interests

- **Cancer genomics and microsatellite instability:** computational detection of MSI from DNA sequencing and from bulk and single-cell gene expression data.
- **Genome assembly and variant benchmarking:** haplotype-resolved assemblies and reference resources for evaluating variant calls, including challenging genomic regions.
- **Long-read genomics:** applications of high-fidelity sequencing to genome assembly and genetic variation analysis.

## Selected publications

{% assign selected_publications = site.publications | sort: "date" | reverse %}
{% for paper in selected_publications %}
- [{{ paper.title }}]({{ paper.paperurl }}) — *{{ paper.venue }}*, {{ paper.date | date: "%Y" }}.
{% endfor %}

See [publication details]({{ '/publications/' | relative_url }}) and my [Google Scholar profile](https://scholar.google.com/citations?user=KSYdspwAAAAJ&hl=en) for further work.

## Academic profiles and contact

[Google Scholar](https://scholar.google.com/citations?user=KSYdspwAAAAJ&hl=en) · [ORCID](https://orcid.org/0000-0002-3429-919X) · [GitHub](https://github.com/PengJia6) · [XJTU faculty profile](https://gr.xjtu.edu.cn/pengjia/zh_CN/zhym/977794/list/index.htm)

Email: [pengjia@xjtu.edu.cn](mailto:pengjia@xjtu.edu.cn)
