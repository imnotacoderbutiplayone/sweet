File "/mount/src/sweet/match_play_app.py", line 570, in <module>
    save_bracket_data(bracket_df)
File "/mount/src/sweet/match_play_app.py", line 384, in save_bracket_data
    response = supabase.table("bracket_data").insert(data).execute()
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/postgrest/_sync/request_builder.py", line 78, in execute
    raise APIError(r.json())
