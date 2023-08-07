import requests
from bs4 import BeautifulSoup
import json


#List of bbc elements. Eventually this will be a mapping between source and targets.
BBC_RSS_ELEMENTS = {'title': 'title', 'desc': 'description', 'url': 'link', 'publication_date': 'pubDate'}


def get_articles_list(rss_url: str) -> [{}]:
    articles = []
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'xml')
    parent_title = soup.find('title').text
    for item in soup.find_all('item'):
        article = {'parent_title': parent_title}
        for element in BBC_RSS_ELEMENTS:
            if item.find(BBC_RSS_ELEMENTS[element]):
                article[element] = item.find(BBC_RSS_ELEMENTS[element]).text
        articles.append(article)
    return articles


#unpicking, very manual for first instance
def get_article(article: {}) -> {}:
    url = article['url']
    article_dict = {'publication_date': article['publication_date'],
                    'url': url,
                    'parent': article['parent_title'],
                    'linked_title': article['title'],
                    'linked_desc': article['desc']}
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    article_body = soup.find(attrs={'id':'main-content'})
    if article_body:
        article_title = article_body.find(attrs={'id': 'main-heading'})
        if article_title:
            article_dict['article_title'] = article_title.text
        #related?
        video_block = article_body.find(attrs={'data-component': 'video-block'})
        if video_block:
            fig_caption = video_block.find('figcaption')
            if fig_caption:
                article_dict['fig_caption'] = fig_caption.find('p').text
        byline_block = article_body.find(attrs={'data-component': 'byline-block'})
        if byline_block:
            article_dict['byline'] = byline_block.text
        text_blocks = article_body.find_all(attrs={'data-component': 'text-block'})
        bold_text = [text_block.text for text_block in text_blocks if text_block.find('b')]
        reg_text = [text_block.text for text_block in text_blocks if text_block.text not in bold_text]
        article_dict['bold'] = bold_text
        article_dict['text'] = reg_text
        if topic_list := article_body.find(attrs={'data-component': 'topic-list'}):
            if topic_list_title := topic_list.find('h2'):
                article_dict['list_title'] = topic_list_title.text
            for i, list_item in enumerate(topic_list.find_all('li')):
                article_dict[f'list_item_{i}'] = list_item.text
                article_dict[f'list_item_{i}_link'] = list_item.find('a')['href']
    else:
        print(f'No main-body found for {url}')
    return article_dict


all_articles = []
urls = ['http://feeds.bbci.co.uk/news/world/rss.xml',
        'http://feeds.bbci.co.uk/news/uk/rss.xml']
for url in urls:
    all_articles += get_articles_list(url)

#print(json.dumps(all_articles, indent=4))

article_data = []
for article in all_articles:
    if 'url' in article:
        article_data.append(get_article(article))


with open('data.json', 'w') as outfile:
    outfile.write(json.dumps(article_data, indent=4))