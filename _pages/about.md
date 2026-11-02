---
permalink: /
title: "About me"
author_profile: true
redirect_from:
  - /about/
  - /about.html
---

{% capture intro_en %}
I am Peng Jia (贾鹏), a researcher at the First Affiliated Hospital of Xi'an Jiaotong University, China. My work focuses on computational methods for genome analysis, with interests in microsatellite instability, long-read sequencing, genome assembly, and variant benchmarking.

## Education

{% include career-list.html kind="education" language="en" %}

## Work Experience

{% include career-list.html kind="work" language="en" %}

## Research interests

- **Cancer genomics and microsatellite instability:** computational detection of MSI from DNA sequencing and from bulk and single-cell gene expression data.
- **Genome assembly and variant benchmarking:** haplotype-resolved assemblies and reference resources for evaluating variant calls, including challenging genomic regions.
- **Long-read genomics:** applications of high-fidelity sequencing to genome assembly and genetic variation analysis.
{% endcapture %}
<div data-language-content="en" lang="en">
{{ intro_en | markdownify }}
</div>

{% capture intro_zh %}
我叫贾鹏，目前在西安交通大学第一附属医院从事研究工作。我的研究主要围绕基因组分析计算方法展开，关注微卫星不稳定性、长读长测序、基因组组装与变异检测评估。

## 教育经历

{% include career-list.html kind="education" language="zh" %}

## 工作经历

{% include career-list.html kind="work" language="zh" %}

## 研究方向

- **肿瘤基因组学与微卫星不稳定性：** 基于 DNA 测序、群体及单细胞基因表达数据的微卫星不稳定性检测方法。
- **基因组组装与变异检测评估：** 单倍型分辨的基因组组装，以及用于评估变异检测的参考资源，尤其关注复杂基因组区域。
- **长读长基因组学：** 高保真测序在基因组组装与遗传变异分析中的应用。
{% endcapture %}
<div data-language-content="zh" lang="zh-CN">
{{ intro_zh | markdownify }}
</div>

<h2 data-en="Selected publications" data-zh="代表性论文">Selected publications</h2>


{% include publication-list.html selected_only=true %}


{% capture contact_en %}
See [publication details]({{ '/publications/' | relative_url }}) and my [Google Scholar profile](https://scholar.google.com/citations?user=KSYdspwAAAAJ&hl=en) for further work.

## Academic profiles and contact

[Google Scholar](https://scholar.google.com/citations?user=KSYdspwAAAAJ&hl=en) · [ORCID](https://orcid.org/0000-0002-3429-919X) · [GitHub](https://github.com/PengJia6) · [XJTU faculty profile](https://gr.xjtu.edu.cn/pengjia/zh_CN/zhym/977794/list/index.htm)

Email: {{ site.author.email_display | escape }}
{% endcapture %}
<div data-language-content="en" lang="en">
{{ contact_en | markdownify }}
</div>

{% capture contact_zh %}
更多研究成果请见[论文列表]({{ '/publications/' | relative_url }})和我的 [Google Scholar 主页](https://scholar.google.com/citations?user=KSYdspwAAAAJ&hl=en)。

## 学术主页与联系方式

[Google Scholar](https://scholar.google.com/citations?user=KSYdspwAAAAJ&hl=en) · [ORCID](https://orcid.org/0000-0002-3429-919X) · [GitHub](https://github.com/PengJia6) · [西安交通大学教师主页](https://gr.xjtu.edu.cn/pengjia/zh_CN/zhym/977794/list/index.htm)

电子邮箱：{{ site.author.email_display | escape }}
{% endcapture %}
<div data-language-content="zh" lang="zh-CN">
{{ contact_zh | markdownify }}
</div>
