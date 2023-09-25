import logging
import threading, time, functools
from configparser import ConfigParser
from datetime import datetime
from os import environ

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from utilities.logging import get_logger
from utilities.utils import get_driver, str_to_timedelta, add_data_redis, update_redis_status, actions_on_page, text_filter, read_url_redis
from utilities.redis import RedisClient
from utilities.queue import QueueClient


# read config file
config_parser = ConfigParser()
config_parser.read('conf/caesars.conf')
module_conf = config_parser["MODULE"]

# init logging
logger_name = environ.get('football_caesarsprop_get_logger', 'football_caesars_prop')
# for local logs storage and stdout use DEBUG_FLAG = 1
DEBUG_FLAG = environ.get('PROP_LOG_DEBUG_FLAG', 0)
log_level = environ.get('football_caesarsprop_log_level', 'WARNING')

logger = get_logger(logger_name, DEBUG_FLAG, log_level)

# other variables
# URL = environ['caesars_prop_url']
# file_tail = URL.split('/')[-1]
hostname = environ.get("HOSTNAME", "local")
sportsbook = environ.get("sportsbook", "none")
URL = None
file_tail = None

redisClient = RedisClient()

module_work_duration = str_to_timedelta(environ.get('football_caesarsprop_module_work_duration', module_conf.get('module_work_duration')))
update_frequency = str_to_timedelta(environ.get('football_caesarsprop_update_frequency', module_conf.get('update_frequency')))
browser = environ.get('football_caesarsprop_browser', module_conf.get('browser_prop'))

scrap_step = int(environ.get('football_scrap_step', module_conf.get('scrap_step')))
scrap_limit = int(environ.get('football_scrap_limit', module_conf.get('scrap_limit')))
local_testing = int(environ.get('football_local_testing', module_conf.get('local_testing')))

# init web driver
# driver.get(URL)

driver = get_driver(browser)

logger.warning(f'Module started working with parameters:\nURL: {URL}\nmodule_work_duration: {module_work_duration}\nupdate_frequency: {update_frequency}\nbrowser: {browser}\nlogger_name: {logger_name}\nlog_level: {log_level}\nDEBUG_FLAG: {DEBUG_FLAG}')


def games_time():
    try:
        timing = driver.find_elements(By.XPATH, ".//div[@class='current-time']")
        times = [game_time.text for game_time in timing]
        times = times[0]
    except:
        times = ' '
        pass
    return times


def check_timeout(game_time=str):
    if game_time == 'HALFTIME':
        return 1
    else:
        try:
            gt = games_time.split(' ')
            if gt[1] == '00:00':
                return 1
            else:
                return 0
        except:
            return 0

def format_bet_name(bt_name, bt_str):
    if '1st' in bt_str:
       return f'1st Quarter {bt_name}'
    elif '2nd' in bt_str:
       return f'2nd Quarter {bt_name}'
    elif '3rd' in bt_str:
       return f'3rd Quarter {bt_name}'
    elif '4th' in bt_str:
       return f'4th Quarter {bt_name}'
    else:
        return bt_name


def scrape_spread(match_row, teams, game_time):
    try:
        bet_name = match_row.find_element(By.XPATH, ".//span[@class='title']").text
        bet_name = format_bet_name('Spread', bet_name)
        outcome = match_row.find_elements(By.XPATH, ".//div[@class='outcome']")

        btn_odds = match_row.find_elements(By.XPATH, ".//button")

        bet_type = [
            outcome[0].find_element(By.XPATH, ".//div[@class='outcomeTitle']").text + ' ' +  btn_odds[0].text.split('\n')[0],
            outcome[-1].find_element(By.XPATH, ".//div[@class='outcomeTitle']").text + ' ' +  btn_odds[-1].text.split('\n')[0],
        ]

        odds = [
            btn_odds[0].text.split('\n')[-1],
            btn_odds[-1].text.split('\n')[-1]
        ]


        home_team = teams[1]
        away_team = teams[0]
        aligned_bet_name = bet_name
        aligned_bet_type = [
            'Away Team' + ' ' +  btn_odds[0].text.split('\n')[0],
            'Home Team' + ' ' +  btn_odds[-1].text.split('\n')[0],
        ]

        period_type = 'Quarter'
        try:
            period_value = game_time.split(' ')[0]
            period_time = game_time.split(' ')[1]
        except:
            period_value = ''
            period_time = ''

        return {
                'bet_name': bet_name,
                'bet_type': bet_type,
                'odds': odds,
                'home_team': home_team,
                'away_team': away_team,
                'aligned_bet_name': aligned_bet_name,
                'aligned_bet_type': aligned_bet_type,
                'period_type': period_type,
                'period_value': period_value,
                'period_time': period_time,
            }
    except Exception as error:
        pass
    
    return 'FAILED'

def scrape_total_points(match_row, teams, game_time):
    try:
        bet_name = match_row.find_element(By.XPATH, ".//span[@class='title']").text
        bet_name = format_bet_name('Total Points', bet_name)
        outcome = match_row.find_elements(By.XPATH, ".//div[@class='outcome']")
        btn_odds = match_row.find_elements(By.XPATH, ".//button")
        bet_type_1 = outcome[0].find_element(By.XPATH, ".//div[@class='outcomeTitle']").text.replace('Over', 'O').replace('Under', 'U')
        bet_type_2 = outcome[-1].find_element(By.XPATH, ".//div[@class='outcomeTitle']").text.replace('Over', 'O').replace('Under', 'U')
        bet_type = [
            bet_type_1 + ' ' +  btn_odds[0].text.split('\n')[0],
            bet_type_2 + ' ' +  btn_odds[-1].text.split('\n')[0],
        ]
        odds = [
            btn_odds[0].text.split('\n')[-1],
            btn_odds[-1].text.split('\n')[-1]
        ]

        home_team = teams[1]
        away_team = teams[0]
        aligned_bet_name = bet_name
        aligned_bet_type = [
            bet_type_1 + ' ' +  btn_odds[0].text.split('\n')[0],
            bet_type_2 + ' ' +  btn_odds[-1].text.split('\n')[0],
        ]
        period_type = 'Quarter'
        try:
            period_value = game_time.split(' ')[0]
            period_time = game_time.split(' ')[1]
        except:
            period_value = ''
            period_time = ''

        return {
                'bet_name': bet_name,
                'bet_type': bet_type,
                'odds': odds,
                'home_team': home_team,
                'away_team': away_team,
                'aligned_bet_name': aligned_bet_name,
                'aligned_bet_type': aligned_bet_type,
                'period_type': period_type,
                'period_value': period_value,
                'period_time': period_time,
            }
    except:
        pass
    
    return 'FAILED'


def scrape_money_line(match_row, teams, game_time):
    try:
        bet_name = match_row.find_element(By.XPATH, ".//span[@class='title']").text
        bet_name = format_bet_name('Moneyline', bet_name)
        outcome = match_row.find_elements(By.XPATH, ".//div[@class='outcome']")
        btn_odds = match_row.find_elements(By.XPATH, ".//button")
        bet_type = [
            outcome[0].find_element(By.XPATH, ".//div[@class='outcomeTitle']").text,
            outcome[-1].find_element(By.XPATH, ".//div[@class='outcomeTitle']").text,
        ]
        odds = [
            btn_odds[0].text.split('\n')[-1],
            btn_odds[-1].text.split('\n')[-1]
        ]
        home_team = teams[1]
        away_team = teams[0]
        aligned_bet_name = bet_name
        aligned_bet_type = [
            'Away Team',
            'Home Team',
        ]
        period_type = 'Quarter'
        
        try:
            period_value = game_time.split(' ')[0]
            period_time = game_time.split(' ')[1]
        except:
            period_value = ''
            period_time = ''

        return {
                'bet_name': bet_name,
                'bet_type': bet_type,
                'odds': odds,
                'home_team': home_team,
                'away_team': away_team,
                'aligned_bet_name': aligned_bet_name,
                'aligned_bet_type': aligned_bet_type,
                'period_type': period_type,
                'period_value': period_value,
                'period_time': period_time,
            }
    except:
        pass
    
    return 'FAILED'



def scrape_popular():
    prop_bets = []
    teams = driver.find_element(By.XPATH, ".//div[@class='teams']").text
    teams = teams.title().split('\n')
    game_name = f'{teams[0] + " @ " + teams[1]}'
    try:
        quarter_half = False
        btn_ul = driver.find_element(By.XPATH, ".//ul[@class='PillSlider ']")
        for btn_li in btn_ul.find_elements(By.XPATH, ".//button[@class='pill-button']"):
            btn_li.click()
            if 'Quarter' in btn_li.text :
                try:
                    quarter_half = True
                    break
                except Exception as e:
                   logger.warning(e)
        
        time_stamp = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        sport = 'Football'
        
        game_time = games_time()
        if not game_time:
            return 'FINISH'
        
        is_timeout = check_timeout(game_time)    
        quarter_half = True  

        if quarter_half:                
            match_rows_pop = driver.find_elements(By.XPATH, ".//div[contains(@class, 'MarketCard')]")
            for idx, match_row in enumerate(match_rows_pop):
                if idx == 0:
                    continue
                bet_name = match_row.find_element(By.XPATH, ".//span[@class='title']").text
                if 'Spread' in bet_name:
                    sprd = scrape_spread(match_row, teams, game_time)
                    if sprd == 'FAILED':
                      logger.info('Spread bet was stopped')
                    else:
                        for i in range(2):
                            prop_info_dict_pop_ml = {
                                'SPORT': sport,
                                'GAME_TYPE': "Live",
                                'IS_PROP': 1,
                                'GAME_NAME': game_name,
                                'BET_NAME': sprd['bet_name'],
                                'BET_TYPE': sprd['bet_type'][i],
                                'ODDS': sprd['odds'][i],
                                'HOME_TEAM': sprd['home_team'],
                                'AWAY_TEAM': sprd['away_team'],
                                'ALIGNED_BET_NAME': sprd['aligned_bet_name'],
                                'ALIGNED_BET_TYPE':  sprd['aligned_bet_type'][i],
                                'PERIOD_TYPE': sprd['period_type'],
                                'PERIOD_VALUE': sprd['period_value'],
                                'PERIOD_TIME': sprd['period_time'],
                                'IS_TIMEOUT': is_timeout,
                                'SPORTS_BOOK': 'Caesars',
                                'TIMESTAMP': time_stamp,
                                'URL': URL
                            }
                            prop_bets.append(prop_info_dict_pop_ml)
                elif 'Total' in bet_name:
                    tps = scrape_total_points(match_row, teams, game_time)
                    
                    if sprd == 'FAILED':
                      logger.info('Total bet was stopped')
                    else:
                        for i in range(2):
                            prop_info_dict_pop_ml = {
                                'SPORT': sport,
                                'GAME_TYPE': "Live",
                                'IS_PROP': 1,
                                'GAME_NAME': game_name,
                                'BET_NAME': tps['bet_name'],
                                'BET_TYPE': tps['bet_type'][i],
                                'ODDS': tps['odds'][i],
                                'HOME_TEAM': tps['home_team'],
                                'AWAY_TEAM': tps['away_team'],
                                'ALIGNED_BET_NAME': tps['aligned_bet_name'],
                                'ALIGNED_BET_TYPE':  tps['aligned_bet_type'][i],
                                'PERIOD_TYPE': tps['period_type'],
                                'PERIOD_VALUE': tps['period_value'],
                                'PERIOD_TIME': tps['period_time'],
                                'IS_TIMEOUT': is_timeout,
                                'SPORTS_BOOK': 'Caesars',
                                'TIMESTAMP': time_stamp,
                                'URL': URL
                            }
                            prop_bets.append(prop_info_dict_pop_ml)
                else:
                    mll = scrape_money_line(match_row, teams, game_time)
                    if mll == 'FAILED':
                      logger.info('Moneylines bet was stopped')
                      print('Moneylines bet was stopped')
                    else:
                        for i in range(2):
                            prop_info_dict_pop_ml = {
                                'SPORT': sport,
                                'GAME_TYPE': "Live",
                                'IS_PROP': 1,
                                'GAME_NAME': game_name,
                                'BET_NAME': mll['bet_name'],
                                'BET_TYPE': mll['bet_type'][i],
                                'ODDS': mll['odds'][i],
                                'HOME_TEAM': mll['home_team'],
                                'AWAY_TEAM': mll['away_team'],
                                'ALIGNED_BET_NAME': mll['aligned_bet_name'],
                                'ALIGNED_BET_TYPE':  mll['aligned_bet_type'][i],
                                'PERIOD_TYPE': mll['period_type'],
                                'PERIOD_VALUE': mll['period_value'],
                                'PERIOD_TIME': mll['period_time'],
                                'IS_TIMEOUT': is_timeout,
                                'SPORTS_BOOK': 'Caesars',
                                'TIMESTAMP': time_stamp,
                                'URL': URL
                            }
                            prop_bets.append(prop_info_dict_pop_ml)

    except:
        pass
    else:
        if not prop_bets:
            return 'STOP'
        elif len(prop_bets) > 0:
            logger.info(f'Game is scraped successfully')
            return prop_bets

def scraper(url_to_scrape):
    module_operate_until = datetime.now() + module_work_duration

    failure_count = 0
    count_of_stopped = 0
    count_scraps = 0

    while datetime.now() < module_operate_until:
        global URL
        global driver
        global file_tail
        
        URL = url_to_scrape
        driver.get(URL)
        file_tail = URL.split('/')[-1]

        parsing_start_time = time.time()
        try:
            logger.info(f'Start scraping')
            try:
                # get all live games
                games_on_initial_page = driver.find_elements(By.XPATH, "//div[@class='MarketCollection']")
            except:
                logger.info('The game has ended')
                res_upd = update_redis_status(URL, 2)
                logger.info(res_upd)
                # break
                continue
            
            popular_bet_list = scrape_popular()

            if popular_bet_list == 'STOP':
                logger.warning('Bets were stopped')
                count_of_stopped += 1
            elif popular_bet_list == 'FINISH':
                logger.info("The game has ended")
                res_upd = update_redis_status(URL, 2)
                logger.info(res_upd)
                # break
                continue

            else:
                if not popular_bet_list:
                    time.sleep(10)
                    continue
                # save data to redis db
                saving_result = add_data_redis(f'football_caesars_prop_{file_tail}', popular_bet_list)
                logger.info(
                    f'The result of saving data: {saving_result}') if saving_result == 'OK' else logger.exception(
                    f'The result of saving data: {saving_result}')                
                count_scraps += 1

            if count_of_stopped == 10:
                logger.warning('The game does not accept bets!')
                res_upd = update_redis_status(URL, 3)
                logger.info(res_upd)
                count_of_stopped = 0

            parsing_work_time = time.time() - parsing_start_time
            time.sleep(max(0, update_frequency.total_seconds() - parsing_work_time))
            time.sleep(10)

            failure_count = 0

        except KeyboardInterrupt:
            logger.warning("Keyboard Interrupt. Quit the driver!")
            driver.quit()
            logger.warning(f'Module stopped working')
            res_upd = update_redis_status(URL, 2)
            logger.info(res_upd)
            # break
            continue

        except Exception as e:
            logger.warning(f'Stop loop with errors:\n{e}')
            failure_count += 1
            if failure_count >= 5:
                driver.quit()
                logger.warning(f'Script exited after {failure_count} unsuccessful attempts to start the main loop')
                res_upd = update_redis_status(URL, 3)
                logger.info(res_upd)
                break
                
        if count_scraps % scrap_step == 0:
            actions_on_page(driver=driver, class_name="listIconWrapper")
            if count_scraps == scrap_limit:
                driver.refresh()                
                count_scraps = 0

        parsing_work_time = time.time() - parsing_start_time
        time.sleep(max(0, update_frequency.total_seconds() - parsing_work_time))

    driver.quit()
    res_upd = update_redis_status(URL, 2)
    logger.info(res_upd)
    logger.warning('Script successfully ended working at the set time')


def with_read_url_redis():
    urls = read_url_redis('caesars')
    for redis_url in urls:
        scraper(redis_url[1])

def with_queuse_client():
    queue = QueueClient()

    def do_work(ch, delivery_tag, body):
        thread_id = threading.get_ident()
        logger.warning('Thread id: %s Deliver Tag: %s Message Body: %s', thread_id, delivery_tag, body)
        url_to_scrape = str(body.decode('UTF-8'))

        cb = None
        try:
            redisClient.update_redis_status(url_to_scrape, 1, {"state": "scraping"})
            scraper(url_to_scrape)
            cb = functools.partial(queue.ack_message, ch, delivery_tag)
        except Exception as ex:
            logger.exception(ex)
            time.sleep(60)
            logger.warning("sleeping 60")
            cb = functools.partial(queue.nack_message, ch, delivery_tag)

        queue.connection.add_callback_threadsafe(cb)

    def on_message(ch, method_frame, _header_frame, body, args):
        threads = args
        delivery_tag = method_frame.delivery_tag
        t = threading.Thread(target=do_work, args=(ch, delivery_tag, body))
        t.start()
        threads.append(t)

    queue.exchange_declare()
    queue.queue_declare(sportsbook, durable=True)
    queue.queue_bind(sportsbook)
    queue.channel.basic_qos(prefetch_count=1)

    threads = []
    on_message_callback = functools.partial(on_message, args=(threads))

    print("Waiting to receive games...")
    queue.channel.basic_consume(on_message_callback=on_message_callback, queue=sportsbook, consumer_tag=hostname)
    queue.channel.start_consuming()

    for thread in threads:
        thread.join()

    queue.connection.close()


def main():
    if local_testing:
        with_read_url_redis()
    else:
        with_queuse_client()


if __name__ == "__main__":
    main()
