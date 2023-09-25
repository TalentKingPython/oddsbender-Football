import requests
import yaml
from kubernetes import client, config
from os import environ, path
import os

#Constants
IN_CLUSTER = environ.get('IN_CLUSTER', default=False)
NAMESPACE = environ.get('KUBE_NAMESPACE', default='prod-oddsbender')
SCALE_CONFIG_PATH = environ.get('SCALE_CONFIG_PATH', default='./scale_config.yaml')
KUBERNETES_PREFIX = environ.get('KUBERNETES_PREFIX', default='')

# API URLS
NCAAFB_URL = "https://data.ncaa.com/casablanca/scoreboard/football/fbs/2023/04/scoreboard.json"
NFL_URL = ""
def main():
	# Get NFL Events
	live_nfl = get_nfl_games()

	#Get NCAAFB Events
	live_ncaa_fb = get_ncaafb_games()
	
	#Get NBA Events
	# live_nba = check_for_live_games(get_events('basketball', 'nba'))
	live_nba = False

	# Get NCAABB Events
	# live_ncaa_bb = check_for_live_games(get_events('basketball', 'mens-college-basketball'))
	live_ncaa_bb = False

	print(f'NFL: {live_nfl}')
	print(f'NCAA FB: {live_ncaa_fb}')
	print(f'NBA: {live_nba}')
	print(f'NCAA BB: {live_ncaa_bb}')
	
	if live_nfl or live_ncaa_fb:
		scale("up", "football")
	
	if live_nba or live_ncaa_bb:
		scale("up", "basketball")
	
	if not live_nfl and not live_ncaa_fb and not live_nba and not live_ncaa_bb:
		scale("down", "all")

	scale("up", "football")

def get_nfl_games():
	#Get Game Data
	api_base_url = "https://site.web.api.espn.com/apis/v2/scoreboard/header"
	parameters = {
		'sport': "football",
		'league': "NFL",
		'region': 'us',
		'lang': 'en',
		'contentorigin': 'espn',
		'tz': 'America%2FNew_York'
	}
	response = requests.get(api_base_url, params=parameters)
	
	events = []
	
	if response.status_code == 200:
		data = response.json()
		events = data['sports'][0]['leagues'][0]['events']
	else:
		print(f'Error getting events data for NFL')
		return None

	#check for live games
	live_games = False
	if events:
		for event in events:
			if event['status'] == 'in':
				live_games = True
		return live_games
	else:
		print("No NFL events found")
		return None

def get_ncaafb_games():
	#Get Game Data
	api_base_url = "https://data.ncaa.com/casablanca/scoreboard/football/fbs/2023/04/scoreboard.json"
	response = requests.get(api_base_url)

	if response.status_code == 200:
		data = response.json()
		events = data['games']
	else:
		print(f'Error getting events data for NCAA Football')
		return None
	
	#check for live games
	live_games = False
	if events:
		for event in events:
			if event['game']['gameState'] == 'live':
				live_games = True
		return live_games
	else:
		print("No NCAA Football events found")
		return None

def scale(scale_type, sport):
	#Get Scraper Config
	scale_config = get_scale_config()
	
	#Init Kubernetes
	if IN_CLUSTER:
		config.load_incluster_config()
	else:
		config.load_kube_config()
	
	#Init Apps
	kube_v1_apps = client.AppsV1Api()

	for item in scale_config:
		name = KUBERNETES_PREFIX + item['name']
		#Set replicas
		if scale_type == 'up':
			replicas = item['up']
		elif scale_type == 'down':
			replicas = item['down']
		
		try:
			if sport in name or item.get('core') or sport == 'all':
				#Scale Objects
				if item['kind'] == 'deployment':
					kube_v1_apps.patch_namespaced_deployment_scale(name=name, namespace=NAMESPACE, body={"spec": {"replicas": replicas}});
					print(f'Scaling deployment [{item["name"]}] to [{replicas}]')
				elif item['kind'] == 'statefulset':
					kube_v1_apps.patch_namespaced_stateful_set_scale(name=name, namespace=NAMESPACE, body={"spec": {"replicas": replicas}});
					print(f'Scaling statefulset [{item["name"]}] to [{replicas}]')
				else:
					raise Exception(f'Unknown kind {item["kind"]}')
		except client.exceptions.ApiException as e:
			if e.reason == "Not Found":
				print(f'Object {item["name"]} not found, skipping')
				continue
			else:
				raise e 

def get_scale_config():
	if path.exists(SCALE_CONFIG_PATH):
		try:
			with open(SCALE_CONFIG_PATH) as f:
				return yaml.safe_load(f)
		except yaml.YAMLError as e:
			print(f"Error reading YAML file: {e}")
		except FileNotFoundError:
			print(f"File not found: {SCALE_CONFIG_PATH}")

	else:
		print(f'File {SCALE_CONFIG_PATH} not found')
		return None


if __name__ == '__main__':
	main()