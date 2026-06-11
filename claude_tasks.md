# Development task for the carbon_dashboard

## general instructions always valid

[Context]Simple dashboard containing satellite derived information for a specific area, maybe with zonal statistics and historical dynamic. The objective is to support operations (current situation snapshot) and demonstrate improvements or changes (long term)

[aim]Support me in implementing code for dat wrangling and engineering following specific tasks indicated below

[detailed instructions]

1. Do not try to complete the whole project in one go, only complete the tasks indicated in the current task sections of this document. also before anything read the file MEMORY.md
  
2. Before writing code or executing an action, plan and explain carefully what is your plan for the task in the document MEMORY.md. Ask for my input before proceeding with implementation
  
3. Always follow test_driven development: write tests in a simple way (avoid as far as possible any fixture or complicated test strcuture) and ask for my input first, then proceed with development and run them often to verify development.
IMPORTANT: before considering a task finished, all tests for that task should be green
test should follow the pattern below:
  
```
   # --
  
   INPUT_create_new_project_data = {
       "prefix": TEMP_FOLDER / "project",
       "project_id": "ABCD123",
       "project_name": "Sample Project",
       "project_description": "This is a sample project description.",
       "contact_person": "John Doe",
       "contact_email": "john.doe@example.com",
       "data_sharing_agreement": "True",
       "sear_provided": "sensor_001",
       "ds_project_owner": "DigitSoil User",
       "additional_data_link": "https://example.com/additional_data",
   }
  
   EXPECTED_create_new_project = [
       (
           "ABCD123",
           "Sample Project",
           "This is a sample project description.",
           "John Doe",
           "john.doe@example.com",
           1,
           "sensor_001",
           "DigitSoil User",
           "https://example.com/additional_data",
       )
   ]

def test_create_new_project(
    input=INPUT_create_new_project_data, expected=EXPECTED_create_new_project
):
    output_bool = upload_new_project(**input)
    assert output_bool

    Conn = DbConnector(ProjectSample(), input["prefix"])
    output = Conn.execute(
        f"Select * from Project where project_id='{input['project_id']}'"
    )
    assert output == expected
```

4. Once that script or code for the task is completed, ran a code_simplifier instance that will refactor code to achieve this priorities:
- code is easy to read and simple as possible
- code follows pep8
- the number of abstractions is kept to a minimum
- Extensive docstrings are present at the beginning of each script
5. Always parse this document for updates or new instructions before doing a task
6. Make commits atomic
7. Refer to settings.py for details
8. At the end of each task add notes on what has been done in MEMORY.md

## Current tasks
1. there is something wron in how test inputs are defined. PLease double check and correct
2. Run all tests, identify and correct problems until the tests are all green