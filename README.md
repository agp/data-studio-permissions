Bulk Data Studio permission updater.

Setup:
  uv sync          # install dependencies  
  
  uv run permissions.py                          # print current permissions  (default)  
  uv run permissions.py --add-member EMAIL       # add the given member as VIEWER (use --role EDITOR to override)  
  uv run permissions.py --revoke-member EMAIL    # revoke all permissions for the given member   
  uv run permissions.py --check-missing          # print only reports missing given member or part of member email  
  uv run permissions.py --all-reports            # run against the full reports list (default is the test report only)  
