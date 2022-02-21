import time
import pandas as pd
from requests_html import HTMLSession
from bs4 import BeautifulSoup
import multiprocessing

# display all columns
pd.set_option('display.max_columns', None)


def get_soup_object(url):
    # requests_html to load the javascript then get the html
    session = HTMLSession()
    r = session.get(url)
    r.html.render(timeout=60)
    soup = BeautifulSoup(r.html.raw_html, 'html.parser')
    session.close()

    return soup


# returns the current price of the stock
def get_price(soup):
    price = soup.find('span', {'class': 'Trsdu(0.3s) Fw(b) Fz(36px) Mb(-4px) D(ib)'})
    if price is not None:
        return float(price.text)
    else:
        return None


# returns the price + 10%
def get_call_strike(price):
    return price + price * 0.1


def get_put_strike(price):
    return price - price * 0.1


# returns a list of html code for each calls
def get_calls_table(soup):
    table = soup.find('table', {'class': 'calls W(100%) Pos(r) Bd(0) Pt(0) list-options'})

    if table is not None:
        return table.find_all('tr')
    return None


# returns a list of html code for each puts
def get_puts_table(soup):
    table = soup.find('table', {'class': 'puts W(100%) Pos(r) list-options'})

    if table is not None:
        return table.find_all('tr')
    return None


# returns the current price of the stock using the stock ticker as a parameter
def get_premium(ticker):
    # gets the corresponding yahoo finance page
    url = f'https://finance.yahoo.com/quote/{ticker}/options?p={ticker}'

    # makes the url into a soup object
    soup = get_soup_object(url)

    # current price of the stock
    price = get_price(soup)
    if price is None:
        print(f'Failed to retrieve the price of {ticker}')
        return
    # current price + 10%
    call_strike = get_call_strike(price)
    # current price - 10%
    put_strike = get_put_strike(price)

    # iterate through the table of call strike prices, puts them into a list
    all_strikes = []
    calls = get_calls_table(soup)
    if calls is not None:
        for i in range(1, len(calls)):
            strike = float(calls[i].find('a', {'class': 'C($linkColor) Fz(s)'}).text.replace(',', ''))
            all_strikes.append(strike)
    else:
        print(f'Failed to retrieve the options of {ticker}\n\n')
        return

    # from the list of strikes, find the one closest to the target price
    call_target = min(all_strikes, key=lambda x: abs(x - call_strike))
    put_target = min(all_strikes, key=lambda x: abs(x - put_strike))

    # from the target price, look up the url with all the expiry dates
    call_url = f'https://finance.yahoo.com/quote/{ticker}/options?strike={call_target}&straddle=false'
    put_url = f'https://finance.yahoo.com/quote/{ticker}/options?strike={put_target}&straddle=false'

    # make a new soup object from the new url
    call_soup = get_soup_object(call_url)
    put_soup = get_soup_object(put_url)
    # stores the wanted data in lists to make a dataframe at the end
    dates_list = []
    call_premiums_list = []
    call_premiums_percent_list = []
    put_premiums_list = []
    put_premiums_percent_list = []

    # for the 5 closest expiration dates, returns premium and premium percentage
    for i in range(1, 6):
        calls = get_calls_table(call_soup)
        puts = get_puts_table(put_soup)
        if calls is not None:
            if i < len(calls):
                # iterate through the calls, skips index 0 (table header)
                date = (calls[i]).find('a', {'class': 'C($linkColor) Fz(s)'}).text
                bid = float((calls[i]).find('td', {'class': 'data-col4 Ta(end) Pstart(7px)'}).text)
                ask = float((calls[i]).find('td', {'class': 'data-col5 Ta(end) Pstart(7px)'}).text)
                # takes the bid-ask average and appends them to the list
                average = round((bid + ask) / 2, 2)
                percent = round(average / price * 100, 2)
                dates_list.append(date)
                call_premiums_list.append(average)
                call_premiums_percent_list.append(percent)

            if i < len(puts):
                # do the same thing with the puts
                bid = float((puts[i]).find('td', {'class': 'data-col4 Ta(end) Pstart(7px)'}).text)
                ask = float((puts[i]).find('td', {'class': 'data-col5 Ta(end) Pstart(7px)'}).text)

                average = round((bid + ask) / 2, 2)
                percent = round(average / price * 100, 2)
                put_premiums_list.append(average)
                put_premiums_percent_list.append(percent)

        else:
            print(f'Failed to retrieve the options of {ticker} at the strike of {call_target}\n\n')
            return

    df = pd.DataFrame(list(zip(dates_list, call_premiums_list, call_premiums_percent_list,
                               put_premiums_list, put_premiums_percent_list)),
                      columns=['Expiration Date',
                               f'{call_target} Call', 'Prem %', f'{put_target} Put', 'Prem %'])
    # add an empty column with the name of the ticker
    df[ticker] = ''
    print(df)
    print('\n')
    # df.to_excel(excel_writer=r'C:\Users\Andy Chen\OneDrive - polymtl.ca\Desktop', sheet_name=ticker, index=False)


if __name__ == '__main__':
    # stock list to test with
    stock_list = ['WISH', 'PLTR', 'SOFI', 'MSFT', 'AAPL', 'CLOV', 'PSFE']

    # uses multiprocessing to load all the pages at the same time
    for i in range(len(stock_list)):
        p = multiprocessing.Process(target=get_premium, args=(stock_list[i],))
        p.start()
        time.sleep(5)
