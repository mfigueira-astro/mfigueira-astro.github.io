---
layout: page
title: Publications
permalink: /publications/
description: <a href='https://ui.adsabs.harvard.edu/public-libraries/TXWeVW2YSm6UC0Ten651Xg'>ADS Library</a>
nav: true
nav_order: 1
---
<!-- _pages/publications.md -->
<div class="publications">

<p class="proposals-summary">
{{ site.publication_count }} publications
{% if site.publication_year_min and site.publication_year_max %}({{ site.publication_year_min }}&ndash;{{ site.publication_year_max }}){% endif %}
</p>

{% bibliography -f {{ site.scholar.bibliography }} %}

</div>
