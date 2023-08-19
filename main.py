import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse

from sklearn.feature_extraction.text import CountVectorizer
import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Dictionary mapping RSS elements we're interested in to their actual tags in the RSS.
RSS_ELEMENTS = {
    'linked_title': 'title',
    'linked_desc': 'description',
    'url': 'link',
    'publication_date': 'pubDate'
}


def get_rss_feeds_from_json_file(filepath: str) -> list:
    """Load the RSS feed URLs from a JSON file."""
    with open(filepath, 'r') as file:
        json_data = json.load(file)
    return json_data['rss_feeds']


def fetch_articles_from_rss(rss_url: str, max_articles: int = -1) -> list:
    """
    Fetches and parses articles from the provided RSS URL.
    :param rss_url: URL of the RSS feed.
    :param max_articles: maximum nuber of articles to pull (used for debugging)
    :return: List of dictionaries containing article details.
    """
    articles = []
    response = requests.get(rss_url)
    soup = BeautifulSoup(response.content, 'xml')
    source_title = soup.find('title').text

    for i, item in enumerate(soup.find_all('item')):
        if 0 < max_articles < i:
            break
        article = {'source_title': source_title}
        for element, rss_tag in RSS_ELEMENTS.items():
            rss_element = item.find(rss_tag)
            if rss_element:
                article[element] = rss_element.text
        articles.append(article)
    return articles


def scrape_article_content(article: dict) -> dict:
    """
    Default article scraper when no custom implemented

    :param url: url for the article
    :return: Dictionary with scraped content.
    """
    url = article['url']
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    domain = urlparse(url).netloc.removeprefix('www.')
    default_flag = domain not in ARTICLE_FUNCTIONS
    if default_flag:
        print(f'No scraper found for {domain}; using default')
    scraping_function = scrape_article_content_default if default_flag else ARTICLE_FUNCTIONS.get(domain)
    article_dict = article.copy()
    article_dict.update(scraping_function(soup))
    if not default_flag and (article_dict['article_text'] is None or len(article_dict['article_text']) == 0):
        print(f'Article text missing for scrape from {url}; trying to patch from default')
        default_dict = scrape_article_content_default(soup)
        article_dict = {key: default_dict[key] if not item else item for key, item in article_dict.items()}
    return article_dict


def scrape_article_content_default(soup: BeautifulSoup) -> dict:
    """
    Default article scraper when no custom implemented

    :param soup: soup object for the article
    :return: Dictionary with scraped content.
    """
    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    author = [meta.get('content', '').strip () for meta in soup.find_all('meta', {'name': 'author'})]
    keywords = soup.find('meta', {'name': 'keywords'}) \
        .get('content', '').strip().split(',') if soup.find('meta', attrs={'name': 'keywords'}) else None
    title = soup.find('meta', {'property': 'og:title'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:title'}) else None
    subtitle = soup.find('meta', {'property': 'og:description'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:description'}) else None

    article_text = [p.text.strip() for p in soup.find_all('p')]

    image_captions = []

    return {
        'page_title': page_title,
        'title': title,
        'subtitle': subtitle,
        'author': author,
        'image_captions': image_captions,
        'article_text': article_text,
        'keywords': keywords
    }


def scrape_article_content_bbc(soup: BeautifulSoup) -> dict:
    """
    Scrapes content from a BBC article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """
    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None

    title = soup.find('h1', {'id': 'main-heading'}).text.strip() if soup.find(
        'h1', {'id': 'main-heading'}) else None
    author = [div.text.strip() for div in soup.find_all(
        'div', attrs={'class': lambda e: 'TextContributorName' in e if e else False})]

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


def scrape_article_content_telegraph(soup: BeautifulSoup) -> dict:
    """
    Scrapes content from a Telegraph article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """

    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    author = [meta.get('content', '').strip () for meta in soup.find_all('meta', {'name': 'DCSext.author'})]
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


def scrape_article_content_daily_mail(soup: BeautifulSoup) -> dict:
    """
    Scrapes content from a Daily Mail article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """

    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    author = [meta.get('content', '').strip () for meta in soup.find_all('meta', {'name': 'author'})]
    keywords = soup.find('meta', {'name': 'keywords'}).get('content', '').strip().split(',') if soup.find('meta', {
        'name': 'keywords'}) else None

    subtitle = [li.text.strip() for li in soup.find('ul', attrs={'class': 'mol-bullets-with-font'})
    .find_all('li')] if soup.find('ul', attrs={'class': 'mol-bullets-with-font'}) else None

    title = None
    if article_text_element := soup.find(name='div', attrs={'id': 'js-article-text'}):
        title = article_text_element.find('h2').text if article_text_element.find('h2') else None

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


def scrape_article_content_independent(soup: BeautifulSoup) -> dict:
    """
    Scrapes content from an Independent article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """
    page_title = soup.title.string.strip() if soup.title else None
    author = [meta.get('content', '').strip () for meta in soup.find_all('meta', {'property': 'article:author_name'})]
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


def scrape_article_content_mirror(soup: BeautifulSoup) -> dict:
    """
    Scrapes content from a Mirror article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """
    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    author = [meta.get('content', '').strip () for meta in soup.find_all('meta', {'name': 'author'})]
    keywords = soup.find('meta', {'name': 'keywords'}) \
        .get('content', '').strip().split(',') if soup.find('meta', attrs={'name': 'keywords'}) else None
    title = soup.find('meta', {'property': 'og:title'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:title'}) else None
    subtitle = soup.find('meta', {'property': 'og:description'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:description'}) else None

    article_text, image_captions = [], []
    if article_body := soup.find('div', attrs={'class': 'article-body', 'itemprop': 'articleBody'}):
        article_text = [p.text.strip() for p in article_body.find_all('p')]
        image_captions = [span.text.strip() for span in article_body.find_all('span') if
                          span.parent.name == 'figcaption']

    return {
        'page_title': page_title,
        'title': title,
        'subtitle': subtitle,
        'author': author,
        'image_captions': image_captions,
        'article_text': article_text,
        'keywords': keywords
    }


def scrape_article_content_sun(soup: BeautifulSoup) -> dict:
    """
    Scrapes content from a Sun article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """
    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    title = soup.find('meta', {'property': 'og:title'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:title'}) else None
    subtitle = soup.find('meta', {'property': 'og:description'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:description'}) else None
    author = [rel.text.strip() for rel in soup.find_all('a', {'rel': 'author'})]

    article_text, image_captions = [], []
    if article_body := soup.find('div', attrs={'class': 'article__content'}):
        article_text = [p.text.strip() for p in article_body.find_all('p')]
        image_captions = [span.text.strip() for span in article_body.find_all('span', attrs={'class':'article__media-span'})]

    keywords = [li.text.strip() for li in soup.find('ul', attrs={'class': 'tags__list'}).find_all('li')] if soup.find('ul', attrs={'class': 'tags__list'}) else []

    return {
        'page_title': page_title,
        'title': title,
        'subtitle': subtitle,
        'author': author,
        'image_captions': image_captions,
        'article_text': article_text,
        'keywords': keywords
    }


def scrape_article_content_daily_express(soup: BeautifulSoup) -> dict:
    """
    Scrapes content from a Daily Express article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """
    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    keywords = soup.find('meta', {'name': 'news_keywords'}).get('content', '').strip().split(',') \
        if soup.find('meta', {'name': 'news_keywords'}) else \
        [meta.get('content', '').strip() for meta in soup.find_all('meta', attrs={'property': 'article:tag'})]
    title = soup.find('meta', {'property': 'og:title'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:title'}) else None
    subtitle = soup.find('meta', {'property': 'og:description'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:description'}) else None
    author = [span.text.strip() for span in soup.find('div', attrs={'class': 'main-author'}).find_all('span')] if soup.find('div', attrs={'class': 'main-author'}) else []

    article_text, image_captions = [], []
    if article_body := soup.find('div', attrs={'data-type': 'article-body'}):
        article_text = [div.text.strip() for div in article_body.find_all('div', attrs={'class': 'text-description'}) if 'dont-miss' not in div.get('class', '')]
        image_captions = [span.text.strip() for span in article_body.find_all('span', attrs={'class': 'newsCaption'})]

    return {
        'page_title': page_title,
        'title': title,
        'subtitle': subtitle,
        'author': author,
        'image_captions': image_captions,
        'article_text': article_text,
        'keywords': keywords
    }


def scrape_article_content_metro(soup: BeautifulSoup) -> dict:
    """
    Scrapes content from a Metro article.

    :param soup: Parsed HTML of the article.
    :return: Dictionary with scraped content.
    """

    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    author = [span.text.strip() for span in soup.find_all('span', attrs={'class': 'author-container'})]
    keywords = [meta.get('content', '').strip() for meta in soup.find_all('meta', attrs={'property': 'article:tag'})]
    title = soup.find('meta', {'property': 'og:title'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:title'}) else None
    subtitle = soup.find('meta', {'property': 'og:description'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:description'}) else None

    article_text, image_captions = [], []
    if article_body := soup.find('div', attrs={'class': 'article-body'}):
        article_text = [p.text.strip() for p in article_body.find_all('p')]
        image_captions = [figcaption.text.strip() for figcaption in article_body.find_all('figcaption')]


    return {
        'page_title': page_title,
        'title': title,
        'subtitle': subtitle,
        'author': author,
        'image_captions': image_captions,
        'article_text': article_text,
        'keywords': keywords
    }


def scrape_article_content_huffpost(soup: BeautifulSoup) -> dict:
    """
    Huffpost scraper

    :param soup: soup object for the article
    :return: Dictionary with scraped content.
    """
    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    author = [span.text.strip () for span in soup.find('div', attrs={'class': 'entry__byline__author'}).find_all('span')] \
        if soup.find('div', attrs={'class': 'entry__byline__author'}) else []
    keywords = soup.find('meta', {'name': 'keywords'}) \
        .get('content', '').strip().split(',') if soup.find('meta', attrs={'name': 'keywords'}) else None
    title = soup.find('meta', {'property': 'og:title'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:title'}) else None
    subtitle = soup.find('meta', {'property': 'og:description'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:description'}) else None

    article_text, image_captions = [], []
    if article_body := soup.find('section', attrs={'class': 'entry__content-list'}):
        article_text = [p.text.strip() for p in article_body.find_all('p')]
        image_captions = [figcaption.text.strip() for figcaption in article_body.find_all('figcaption')]

    return {
        'page_title': page_title,
        'title': title,
        'subtitle': subtitle,
        'author': author,
        'image_captions': image_captions,
        'article_text': article_text,
        'keywords': keywords
    }


def scrape_article_content_standard(soup: BeautifulSoup) -> dict:
    """
    standard scraper

    :param soup: soup object for the article
    :return: Dictionary with scraped content.
    """
    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    author = [meta.get('content', '').strip () for meta in soup.find_all('meta', {'name': 'author'})]
    keywords = soup.find('meta', {'name': 'keywords'}) \
        .get('content', '').strip().split(',') if soup.find('meta', attrs={'name': 'keywords'}) else None
    title = soup.find('meta', {'property': 'og:title'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:title'}) else None
    subtitle = soup.find('meta', {'property': 'og:description'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:description'}) else None

    article_text = []
    if article_body := soup.find('div', attrs={'id': 'main'}):
        article_text = [p.text.strip() for p in article_body.find_all('p')]

    image_captions = [figcaption.text.strip() for figcaption in soup.find_all('figcaption')]

    return {
        'page_title': page_title,
        'title': title,
        'subtitle': subtitle,
        'author': author,
        'image_captions': image_captions,
        'article_text': article_text,
        'keywords': keywords
    }


def scrape_article_content_manchester(soup: BeautifulSoup) -> dict:
    """
    Default article scraper when no custom implemented

    :param soup: soup object for the article
    :return: Dictionary with scraped content.
    """
    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    author = [meta.get('content', '').strip () for meta in soup.find_all('meta', {'name': 'author'})]
    keywords = soup.find('meta', {'name': 'keywords'}) \
        .get('content', '').strip().split(',') if soup.find('meta', attrs={'name': 'keywords'}) else None
    title = soup.find('meta', {'property': 'og:title'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:title'}) else None
    subtitle = soup.find('meta', {'property': 'og:description'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:description'}) else None

    article_text, image_captions = [], []
    if article_body := soup.find('div', attrs={'class': 'content-column'}):
        article_text = [p.text.strip() for p in article_body.find_all('p')]
        image_captions = [figcaption.text.strip() for figcaption in article_body.find_all('figcaption')]

    return {
        'page_title': page_title,
        'title': title,
        'subtitle': subtitle,
        'author': author,
        'image_captions': image_captions,
        'article_text': article_text,
        'keywords': keywords
    }


def scrape_article_content_belfast(soup: BeautifulSoup) -> dict:
    """
    Default article scraper when no custom implemented

    :param soup: soup object for the article
    :return: Dictionary with scraped content.
    """
    # Extracting the title
    page_title = soup.title.string.strip() if soup.title else None
    author = [meta.get('content', '').strip () for meta in soup.find_all('meta', {'name': 'author'})]
    keywords = soup.find('meta', {'name': 'keywords'}) \
        .get('content', '').strip().split(',') if soup.find('meta', attrs={'name': 'keywords'}) else None
    title = soup.find('meta', {'property': 'og:title'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:title'}) else None
    subtitle = soup.find('meta', {'property': 'og:description'}) \
        .get('content', '').strip() if soup.find('meta', attrs={'property': 'og:description'}) else None

    image_captions = [figcaption.text.strip() for figcaption in soup.find_all('figcaption')]

    article_text = []
    if article_body := soup.find('div', attrs={'class': 'article-body'}):
        article_text = [p.text.strip() for p in article_body.find_all('p')]


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
    'bbc.co.uk': scrape_article_content_bbc,
    'telegraph.co.uk': scrape_article_content_telegraph,
    'dailymail.co.uk': scrape_article_content_daily_mail,
    'independent.co.uk': scrape_article_content_independent,
    'mirror.co.uk': scrape_article_content_mirror,
    'thesun.co.uk': scrape_article_content_sun,
    'express.co.uk': scrape_article_content_daily_express,
    'metro.co.uk': scrape_article_content_metro,
    'huffingtonpost.co.uk': scrape_article_content_huffpost,
    'standard.co.uk': scrape_article_content_standard,
    'manchestereveningnews.co.uk': scrape_article_content_manchester,
    'belfastlive.co.uk': scrape_article_content_belfast
}

# "https://www.channel4.com/news/feed" removed from param - video based reporting


def fetch_article_data(max_articles: int = -1):
    urls = get_rss_feeds_from_json_file('param.json')

    all_articles = []
    for url in urls:
        all_articles += fetch_articles_from_rss(url, max_articles)

    article_data = [scrape_article_content(article) for article in all_articles if
                    'url' in article]

    # Saving the scraped articles to a JSON file.
    with open('data2.json', 'w') as outfile:
        outfile.write(json.dumps(article_data, indent=4))


def keyword_extraction_test(path: str):
    articles = []
    with open(path, 'r') as file:
        articles = json.load(file)

    n_gram_range = (1, 3)
    stop_words = "english"

    for article in articles:
        sub = article['subtitle'] if type(article['subtitle']) == list else [article['subtitle']] if article['subtitle'] else []
        article['full_text'] = ' '.join(([article['title']] if article['title'] else [])
                                        + sub + [text for text in article['article_text'] if re.sub(r'[^\w\s]', '', text)])

        print(f'\n{article["url"]}')
        doc = article['full_text']
        # Extract candidate words/phrases
        for n in range(1,4):
            count = CountVectorizer(ngram_range=(n, n), stop_words=stop_words).fit([doc])
            candidates = count.get_feature_names_out()

            model = SentenceTransformer('distilbert-base-nli-mean-tokens')
            doc_embedding = model.encode([doc])
            candidate_embeddings = model.encode(candidates)
            top_n = 10
            distances = cosine_similarity(doc_embedding, candidate_embeddings)
            keywords = [candidates[index] for index in distances.argsort()[0][-top_n:]]
            article['keywords_n'] = keywords
            print(f'keywords_{n}: {keywords}')


    # Saving the scraped articles to a JSON file.
    with open('data4.json', 'w') as outfile:
        outfile.write(json.dumps(articles, indent=4))


def main():
    # fetch_article_data()
    keyword_extraction_test('data2.json')


if __name__ == "__main__":
    main()
