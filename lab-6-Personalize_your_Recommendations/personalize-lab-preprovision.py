import json
import boto3
import boto3

import json

import time
from datetime import datetime

personalize = boto3.client('personalize')
personalize_runtime = boto3.client('personalize-runtime')


def lambda_handler(event, context):
    # TODO implement
    
    schema_name="personalize-lab-recommendations-schema"
    personalize_dataset_group_name="personalize-lab-dataset-group"
    data_set_name="personalize-lab-dataset"
    dataset_import_job_name="personalize-recommendations-dataset-import-job1"
    bucket="ee-assets-prod-us-east-1"
    filename="modules/22503d96e66843d8b576f4430f3e4ec7/v3/DEMO-movie-lens-100k.csv"
    account_id=boto3.client('sts').get_caller_identity().get('Account')
    personalize_role_arn="arn:aws:iam::"+account_id+":role/AmazonLabSageMakerRole"
    solution_name="personalize-lab-recommendations-solution"
    solution_version="personalize-lab-recommendations-solution-version"
    
    personalize_schema = {
        "type": "record",
        "name": "Interactions",
        "namespace": "com.amazonaws.personalize.schema",
        "fields": [
            {
                "name": "USER_ID",
                "type": "string"
            },
            {
                "name": "ITEM_ID",
                "type": "string"
            },
            {
                "name": "TIMESTAMP",
                "type": "long"
            }
        ],
        "version": "1.0"
    }
    #create schema if it doesnt exist
    response=personalize.list_schemas()
    schemas=response["schemas"]
    schema_exists=False
    for schema in schemas:
        if schema['name'] == schema_name:
            print("Schema "+schema_name+" already exists, not creating")
            schema_exists=True
            schema_arn = schema['schemaArn']
            break
    if not schema_exists:    
        create_schema_response = personalize.create_schema(
        name = schema_name,
        schema = json.dumps(personalize_schema))
        schema_arn = create_schema_response['schemaArn']
        
    #create dataset group if it doesnt exist
    response=personalize.list_dataset_groups()
    datasetGroups=response['datasetGroups']
    group_exists=False
    for datasetGroup in datasetGroups:
        if datasetGroup['name'] == personalize_dataset_group_name:
            print("dataset group "+personalize_dataset_group_name+" already exists, not creating")
            group_exists=True
            dataset_group_arn = datasetGroup['datasetGroupArn']
            break
    if not group_exists:      
        create_dataset_group_response = personalize.create_dataset_group(name = personalize_dataset_group_name)
        dataset_group_arn = create_dataset_group_response['datasetGroupArn']
    #wait for dataset group to become active
    status = None
    max_time = time.time() + 5*60 # 5 minutes
    while time.time() < max_time:
        describe_dataset_group_response = personalize.describe_dataset_group(
            datasetGroupArn = dataset_group_arn
        )
        status = describe_dataset_group_response["datasetGroup"]["status"]
        print("DatasetGroup: {}".format(status))
        
        if status == "ACTIVE" or status == "CREATE FAILED":
            break
            
        time.sleep(15)
    #create dataset if it doesnt exist
    
    response=personalize.list_datasets(datasetGroupArn=dataset_group_arn)
    datasets=response['datasets']
    dataset_exists=False
    for dataset in datasets:
        if dataset['name'] == data_set_name:
            print("dataset  "+data_set_name+" already exists, not creating")
            dataset_exists=True
            dataset_arn = dataset['datasetArn']
            break
    if not dataset_exists:      
        dataset_type = "INTERACTIONS"
        create_dataset_response = personalize.create_dataset(
            datasetType = dataset_type,
            datasetGroupArn = dataset_group_arn,
            schemaArn = schema_arn,
            name=data_set_name
        )
        dataset_arn = create_dataset_response['datasetArn']
        
    #create dataset import job if it doesnt exist.
    dataset_import_job_exists=False
    response=str(personalize.list_dataset_import_jobs(datasetArn=dataset_arn))
    if response.find(dataset_import_job_name) != -1:
        print("dataset import job "+dataset_import_job_name+" already exists, not creating")
        dataset_import_job_exists=True
        dataset_import_job_arn="arn:aws:personalize:us-east-1:"+account_id+":dataset-import-job/"+dataset_import_job_name
    if not dataset_import_job_exists:
        create_dataset_import_job_response = personalize.create_dataset_import_job(
            jobName =dataset_import_job_name,
            datasetArn = dataset_arn,
            dataSource = {
                "dataLocation": "s3://{}/{}".format(bucket, filename)
            },
            roleArn = personalize_role_arn
        )
        dataset_import_job_arn = create_dataset_import_job_response['datasetImportJobArn']
    status = None
    describe_dataset_import_job_response = personalize.describe_dataset_import_job(
        datasetImportJobArn = dataset_import_job_arn)
    dataset_import_job = describe_dataset_import_job_response["datasetImportJob"]
    if "latestDatasetImportJobRun" not in dataset_import_job:
        status = dataset_import_job["status"]
        print("DatasetImportJob: {}".format(status))
    else:
        status = dataset_import_job["latestDatasetImportJobRun"]["status"]
        print("LatestDatasetImportJobRun: {}".format(status))
    
    if status == "ACTIVE":
        print("Dataset import job status is active, proceeding with next steps")
    else:
        return {
            'statusCode': 200,
            'body': json.dumps('Hello from Lambda!')
        }
    #create a solution if it doesnt exist
    
    recipe_arn = "arn:aws:personalize:::recipe/aws-hrnn"
    response=str(personalize.list_solutions(datasetGroupArn=dataset_group_arn))
    solution_exists=False
    if response.find(solution_name) != -1:
        print("Solution "+solution_name+" Already exists, not creating")
        solution_exists=True
        solution_arn="arn:aws:personalize:us-east-1:"+account_id+":solution/"+solution_name
    if not solution_exists:
        create_solution_response = personalize.create_solution(
            name = solution_name,
            datasetGroupArn = dataset_group_arn,
            recipeArn = recipe_arn)
        solution_arn = create_solution_response['solutionArn']
    time.sleep(30)
    
    #create solution version if it doesnt exist
    
    solution_version_exists=False
    response=personalize.list_solution_versions(solutionArn=solution_arn)
    if response['solutionVersions']:
        print("Solution Version for"+solution_name+" Already exists, not creating")
        solution_version_exists=True
        solution_version_arn=response['solutionVersions'][0]['solutionVersionArn']
        describe_solution_version_response = personalize.describe_solution_version(
            solutionVersionArn = solution_version_arn)
        status = describe_solution_version_response["solutionVersion"]["status"]
        print("SolutionVersion Status is: {}".format(status))
        if status == "ACTIVE":
            print("Solution version status is active")
            return {
                'statusCode': 200,
                'body': json.dumps('Solution version status is active')
            }
         
    if not solution_version_exists:
        create_solution_version_response = personalize.create_solution_version(
            solutionArn = solution_arn)
        solution_version_arn = create_solution_version_response['solutionVersionArn']
    time.sleep(30)
    
    
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
    

