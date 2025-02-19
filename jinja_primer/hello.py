import yaml
from jinja2 import Environment, FileSystemLoader

with open('src/names.yaml', 'r') as fh:
    names = yaml.safe_load(fh)

env = Environment(loader=FileSystemLoader('templates/'))
template = env.get_template('hello.j2')

print(template.render(names))
