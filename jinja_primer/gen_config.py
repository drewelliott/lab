import yaml
from jinja2 import Environment, FileSystemLoader

with open('src/config_data.yaml', 'r') as fh:
    config_data = yaml.safe_load(fh)

env = Environment(loader=FileSystemLoader('templates/'))
template = env.get_template('config.j2')

print(template.render(config_data))
