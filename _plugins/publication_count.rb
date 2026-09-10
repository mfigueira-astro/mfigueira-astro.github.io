module Jekyll
  class PublicationCountGenerator < Generator
    priority :high

    def generate(site)
      bib_file = File.join(site.source, "_bibliography", "papers.bib")
      count = 0
      years = []

      if File.exist?(bib_file)
        content = File.read(bib_file)
        content.scan(/^\s*@\w+\{/) { count += 1 }
        content.scan(/year\s*=\s*\{?(\d{4})\}?/) { |y| years << y[0].to_i }
      end

      site.config["publication_count"] = count
      site.config["publication_year_min"] = years.min
      site.config["publication_year_max"] = years.max
    end
  end
end
