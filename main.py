import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse

# Dictionary mapping RSS elements we're interested in to their actual tags in the RSS.
RSS_ELEMENTS = {
    'linked_title': 'title',
    'linked_desc': 'description',
    'url': 'link',
    'publication_date': 'pubDate'
}


def get_rss_feeds_from_json_file(filepath: str) -> list:
    """
    Loads the RSS feed URLs from the given JSON file.

    :param filepath: Path to the JSON file.
    :return: List of RSS feed URLs.
    """
    with open(filepath, 'r') as file:
        json_data = json.load(file)
    return json_data['rss_feeds']


def get_articles_list(rss_url: str) -> list:
    """
    Fetches and parses articles from the provided RSS URL.

    :param rss_url: URL of the RSS feed.
    :return: List of dictionaries containing article details.
    """
    articles = []
    r = requests.get(rss_url)
    soup = BeautifulSoup(r.content, 'xml')
    source_title = soup.find('title').text

    for item in soup.find_all('item'):
        article = {'source_title': source_title}
        for element, rss_tag in RSS_ELEMENTS.items():
            rss_element = item.find(rss_tag)
            if rss_element:
                article[element] = rss_element.text
        articles.append(article)
    return articles


def get_article(article: dict) -> dict:
    """
    Scrapes the actual article content based on its domain.

    :param article: Dictionary with basic article details.
    :return: Updated dictionary with scraped content.
    """
    url = article['url']
    article_dict = article
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    domain = urlparse(url).netloc.removeprefix('www.')
    if domain in ARTICLE_FUNCTIONS:
        article_dict.update(ARTICLE_FUNCTIONS[domain](soup))
    else:
        print(f'No scraping function found for {domain}')
    return article_dict


def get_article_content_bbc(soup: BeautifulSoup) -> dict:
    """
    Scrapes content from a BBC article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """
    article_details = {}
    article_body = soup.find(attrs={'id': 'main-content'})
    if article_body:
        article_title = article_body.find(attrs={'id': 'main-heading'})
        if article_title:
            article_details['article_title'] = article_title.text
        # related?
        video_block = article_body.find(attrs={'data-component': 'video-block'})
        if video_block:
            fig_caption = video_block.find('figcaption')
            if fig_caption:
                article_details['fig_caption'] = fig_caption.find('p').text
        byline_block = article_body.find(attrs={'data-component': 'byline-block'})
        if byline_block:
            article_details['byline'] = byline_block.text
        text_blocks = article_body.find_all(attrs={'data-component': 'text-block'})
        bold_text = [text_block.text for text_block in text_blocks if text_block.find('b')]
        reg_text = [text_block.text for text_block in text_blocks if text_block.text not in bold_text]
        article_details['bold'] = bold_text
        article_details['text'] = reg_text
        if topic_list := article_body.find(attrs={'data-component': 'topic-list'}):
            if topic_list_title := topic_list.find('h2'):
                article_details['list_title'] = topic_list_title.text
            for i, list_item in enumerate(topic_list.find_all('li')):
                article_details[f'list_item_{i}'] = list_item.text
                article_details[f'list_item_{i}_link'] = list_item.find('a')['href']
    return article_details


def get_article_content_telegraph(soup: BeautifulSoup) -> dict:
    """
    Scrapes content from a Telegraph article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """
    article_details = {}
    article_body = soup.find(attrs={'id': 'main-content'})
    if article_body:
        header = article_body.find('header')
        if header:
            article_title = header.find('h1')
            if article_title:
                article_details['article_title'] = article_title.text
            article_subtitle = header.find('p')
            if article_subtitle:
                article_details['article_subtitle'] = article_subtitle.text
            # related?
        video_block = article_body.find(attrs={'data-component': 'video-block'})
        if video_block:
            fig_caption = video_block.find('figcaption')
            if fig_caption:
                article_details['fig_caption'] = fig_caption.find('p').text
        byline_block = article_body.find_all(attrs={'class': 'e-byline__author'})
        if byline_block:
            article_details['byline'] = [author.text for author in byline_block]
        text_blocks = article_body.find_all(attrs={'itemprop': 'articleBody'})
        bold_text = [text_block.text for text_block in text_blocks if text_block.find('b')]
        reg_text = [text_block.text for text_block in text_blocks if text_block.text not in bold_text]
        article_details['bold'] = bold_text
        article_details['text'] = reg_text
        if topic_list := soup.find(attrs={'class': 'articleList section'}):
            if topic_list_title := topic_list.find(attrs={'class': 'article-list__heading'}):
                article_details['list_title'] = topic_list_title.text
            for i, list_item in enumerate(topic_list.find_all(attrs={'class': 'list-headline'})):
                article_details[f'list_item_{i}'] = list_item.text
                article_details[f'list_item_{i}_link'] = list_item.find('a')['href']
    return article_details


def get_article_content_daily_mail(soup: BeautifulSoup) -> dict:
    """
    Scrapes content from a Daily Mail article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """
    # Extracting the title
    title = soup.title.string.strip() if soup.title else None

    # Extracting the author
    author = soup.find('meta', {'name': 'author'}).get('content', '').strip() if soup.find('meta',
                                                                                           {'name': 'author'}) else None

    # Extracting image captions
    image_captions = [caption.get_text(' ', strip=True) for caption in soup.find_all('figcaption')]

    # Extracting the main article text (paragraphs)
    article_text_div = soup.find('div', class_='article-text')

    # Filtering out paragraphs that are likely not part of the main article (e.g., comments, related articles)
    def is_relevant_paragraph(p):
        lower_text = p.get_text().lower()
        irrelevant_phrases = ["share what you think", "comments below", "views of mailonline"]
        return not any(phrase in lower_text for phrase in irrelevant_phrases)

    paragraphs = [p.get_text(' ', strip=True) for p in article_text_div.find_all('p') if
                  is_relevant_paragraph(p)] if article_text_div else []

    return {
        "title": title,
        "author": author,
        "image_captions": image_captions,
        "text": paragraphs
    }


def get_article_content_independent(soup: BeautifulSoup) -> dict:
    """
    Scrapes content from an Independent article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """
    # Extracting the title
    title = soup.title.string.strip() if soup.title else None

    # Extracting the author
    author = soup.find('meta', {'property': 'article:author_name'}).get('content', '').strip() if soup.find('meta', {
        'property': 'article:author_name'}) else None

    # Attempting to extract the main article text by checking common tags and class names
    article_content = None

    # Check for <article> tag
    if soup.article:
        article_content = soup.article.get_text(' ', strip=True)

    # Check for <div> with class 'article-body' or similar if <article> tag is not present
    if not article_content:
        div_content = soup.find('div', class_='article-body') or soup.find('div', class_='article-content')
        if div_content:
            article_content = div_content.get_text(' ', strip=True)

    # If neither <article> nor <div> with 'article-body' class is found, use <main> tag
    if not article_content:
        if soup.main:
            article_content = soup.main.get_text(' ', strip=True)

    # Extracting image captions
    image_captions = [caption.get_text(' ', strip=True) for caption in soup.find_all('figcaption')]

    # Extracting paragraphs from the main article content
    paragraphs = [p.get_text(' ', strip=True) for p in soup.find_all('p')]

    return {
        "title": title,
        "author": author,
        "image_captions": image_captions,
        "text": paragraphs
    }

# Mapping of domains to their respective scraping functions.
ARTICLE_FUNCTIONS = {
    'bbc.co.uk': get_article_content_bbc,
    'telegraph.co.uk': get_article_content_telegraph,
    'dailymail.co.uk': get_article_content_daily_mail,
    'independent.co.uk': get_article_content_independent
}

# Sample list of URLs (can also be loaded from a JSON file).
# #urls = get_rss_feeds_from_json_file('param.json')
urls = [
 #   "http://feeds.bbci.co.uk/news/world/rss.xml",
 #   "http://feeds.bbci.co.uk/news/uk/rss.xml",
 #   "https://www.telegraph.co.uk/rss.xml",
    "https://www.dailymail.co.uk/home/index.rss",
    "http://www.independent.co.uk/rss"
]

all_articles = []
for url in urls:
    all_articles += get_articles_list(url)

# print(json.dumps(all_articles, indent=4))

article_data = [get_article(article) for article in all_articles if 'url' in article]

# Saving the scraped articles to a JSON file.
with open('data2.json', 'w') as outfile:
    outfile.write(json.dumps(article_data, indent=4))
