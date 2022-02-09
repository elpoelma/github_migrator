from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
import os
from dotenv import dotenv_values
from git import Repo
config = dotenv_values(".env")


transport_source = AIOHTTPTransport(url=config['GITHUB_SOURCE_URL'], headers={'Authorization': f"bearer {config['GITHUB_SOURCE_TOKEN']}"})

client_source = Client(transport=transport_source, fetch_schema_from_transport=True)

# Provide a GraphQL query
query = gql(
    """
    query getRepoCount ($username: String!) {
      user (login: $username) {
        repositories {
            totalCount
        }
      }
    }
"""
)



# Execute the query on the transport
result = client_source.execute(query, variable_values={"username": config["GITHUB_SOURCE_USERNAME"]})
repository_count = result['user']['repositories']['totalCount']


query = gql(
    """
    query getRepos ($username: String!, $repoCount: Int!) {
      user (login: $username) {
        repositories(first: $repoCount) {
            nodes {
                sshUrl
                name
            }
        }
      }
    }
"""
)

repositories = client_source.execute(query, variable_values={"username": config["GITHUB_SOURCE_USERNAME"], "repoCount": repository_count})['user']['repositories']['nodes']


transport_dest = AIOHTTPTransport(url=config['GITHUB_DESTINATION_URL'], headers={'Authorization': f"bearer {config['GITHUB_DESTINATION_TOKEN']}"})
client_dest = Client(transport=transport_dest, fetch_schema_from_transport=True)

mutation = gql(
    """
    mutation addRepo ($name: String!) {
      createRepository(input: {name: $name, visibility: PRIVATE}){
        repository {
          sshUrl
        }
      }
    }
"""
)

query = gql(
      """
    query getRepo ($name: String!, $owner: String!) {
      repository(name: $name, owner: $owner){
        sshUrl
      }
    }
"""
)

for repo in repositories:
    git_repo = Repo.clone_from(repo['sshUrl'], to_path=repo['name'], branch='master')
    remotes = git_repo.remotes
    for remote in remotes:
      git_repo.delete_remote(remote)
    print(repo["name"])
    try:
      result = client_dest.execute(mutation, variable_values={"name": repo['name']})["createRepository"]["repository"]
    except:
      print("Remote repo already exists")
      result = client_dest.execute(query, variable_values={"name": repo['name'], "owner": config["GITHUB_DESTINATION_USERNAME"]})["repository"]

    new_remote = git_repo.create_remote("origin", result["sshUrl"])
    new_remote.push(refspec="master")
    
    os.system(f"rm -rf {repo['name']}")


