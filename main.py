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

    for i, item in enumerate(soup.find_all('item')):
        # Debugging line so we're not testing on hundreds of articles
        if i > 5:
            return articles
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
        article_dict.update(ARTICLE_FUNCTIONS[domain](soup, url))
    else:
        print(f'No scraping function found for {domain}; trying default')
    return article_dict


def get_article_content_bbc(soup: BeautifulSoup, url: str) -> dict:
    """
    Scrapes content from a BBC article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """
    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None

    title = soup.find('h1', {'id': 'main-heading'}).text.strip() if soup.find(
        'h1', {'id': 'main-heading'}) else None
    author = soup.find('div', attrs={'class': lambda e: 'TextContributorName' in e if e else False}) \
        .text.strip() if soup.find('div', attrs={
        'class': lambda e: 'TextContributorName' in e if e else False}) else None

    subtitle, article_text = [], []
    # Extracting from the article body element
    for text_block in soup.find_all(name='div', attrs={'data-component': 'text-block'}):
        if bold_element := text_block.find('b'):
            subtitle.append(bold_element.text.strip())
        elif text_element := text_block.find('p'):
            article_text.append(text_element.text.strip())

    image_captions = []
    for image_block in soup.find_all(name='div', attrs={'data-component': 'image-block'}):
        if image_caption := image_block.text.strip():
            image_captions.append(image_caption)
        if image := image_block.find('img'):
            if alt_text := image.get('alt'):
                image_captions.append(alt_text)

    keywords = [li.text.strip() for li in soup.find('div', attrs={'data-component': 'topic-list'})
            .find_all('li')] if soup.find('div', attrs={'data-component': 'topic-list'}) else None
    return {
        'page_title': page_title,
        'title': title,
        'subtitle': subtitle,
        'author': author,
        'image_captions': image_captions,
        'article_text': article_text,
        'keywords': keywords
    }


def get_article_content_telegraph(soup: BeautifulSoup, url: str) -> dict:
    """
    Scrapes content from a Telegraph article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """

    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    author = soup.find('meta', {'name': 'DCSext.author'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'name': 'DCSext.author'}) else None
    keywords = soup.find('meta', {'name': 'keywords'}) \
        .get('content', '').strip().split(',') if soup.find('meta', attrs={'name': 'keywords'}) else None
    title = soup.find('meta', {'property': 'og:title'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:title'}) else None
    subtitle = soup.find('meta', {'property': 'og:description'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:description'}) else None

    image_captions = [image_caption.text.strip() for image_caption in soup.find_all('figcaption')]
    article_text = [p.text.strip() for p in
                    soup.find(name='div', attrs={'data-test': 'article-body-test'})
                    .find_all('p')] if soup.find(name='div', attrs={'data-test': 'article-body-test'}) else None

    return {
        'page_title': page_title,
        'title': title,
        'subtitle': subtitle,
        'author': author,
        'image_captions': image_captions,
        'article_text': article_text,
        'keywords': keywords
    }


def get_article_content_daily_mail(soup: BeautifulSoup, url: str) -> dict:
    """
    Scrapes content from a Daily Mail article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """

    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    keywords = soup.find('meta', {'name': 'keywords'}).get('content', '').strip().split(',') if soup.find('meta', {
        'name': 'keywords'}) else None

    subtitle = [li.text.strip() for li in soup.find('ul', attrs={'class': 'mol-bullets-with-font'})
        .find_all('li')] if soup.find('ul', attrs={'class': 'mol-bullets-with-font'}) else None

    title = None
    if article_text_element := soup.find(name='div', attrs={'id': 'js-article-text'}):
        title = article_text_element.find('h2').text if article_text_element.find('h2') else None
    author = soup.find('meta', {'name': 'author'}).get('content', '').strip() if soup.find('meta',
                                                                                           {'name': 'author'}) else None
    image_captions, article_text = [], []
    # Extracting from the article body element
    if article_body := soup.find(name='div', attrs={'itemprop': 'articleBody'}):

        all_text = article_body.find_all('p')
        image_captions, article_text = [], []

        for text_element in all_text:
            if text_element.get('class', '') and text_element.get('class', '')[0] == 'imageCaption':
                image_captions.append(text_element.get_text(' ', strip=True))
            else:
                article_text.append(text_element.get_text(' ', strip=True))

    return {
        'page_title': page_title,
        'title': title,
        'subtitle': subtitle,
        'author': author,
        'image_captions': image_captions,
        'article_text': article_text,
        'keywords': keywords
    }


def get_article_content_independent(soup: BeautifulSoup, url: str) -> dict:
    """
    Scrapes content from an Independent article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """
    page_title = soup.title.string.strip() if soup.title else None

    author = soup.find('meta', {'property': 'article:author_name'}).get('content', '').strip() if soup.find('meta', {
        'property': 'article:author_name'}) else None
    keywords = soup.find('meta', {'property': 'keywords'}).get('content', '').strip().split(',') if soup.find('meta', {
        'property': 'keywords'}) else None

    title, subtitle = None, None
    if article_header := soup.find('header', attrs={'id': 'articleHeader'}):
        title = article_header.find('h1').get_text(' ', strip=True) if article_header.find('h1') else None
        subtitle = article_header.find('h2').get_text(' ', strip=True) if article_header.find('h1') else None

    image_captions, article_text = [], []
    if article_body := soup.find('div', attrs={'id': 'main'}):

        all_text = article_body.find_all('p')

        for text_element in all_text:
            if text_element.parent.parent.name == 'figcaption':
                image_captions.append(text_element.get_text(' ', strip=True))
            else:
                article_text.append(text_element.get_text(' ', strip=True))

    return {
        'page_title': page_title,
        'title': title,
        'subtitle': subtitle,
        'author': author,
        'image_captions': image_captions,
        'article_text': article_text,
        'keywords': keywords
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
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "http://feeds.bbci.co.uk/news/uk/rss.xml",
    "https://www.telegraph.co.uk/rss.xml",
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
