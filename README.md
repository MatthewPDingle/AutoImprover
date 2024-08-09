# About

This is a LLM-driven program auto-improver.  You give the program (boot.py, which was written by Claude 3.5 Sonnet) a description of a program you would like made (edit prompts/prompt_initial_sim.txt) and run boot.py.  AutoImprover will use GPT-4o to write an initial version of the program and corresponding unit tests, and then begin a loop of self-improvement.  This loop is outlined in flowchart.png.  Every loop, the program will decide at random whether to try and fix or improve some aspect of the code, or add a new feature.  

## Usage

Clone this repo and make an apikey.txt file in the main directory.  Paste in your OpenAI API key and nothing else.

To use the program, run the following command:

```bash
python boot.py
```

## Notes

- The unit test stuff is all commented out.  I haven't yet been able to get it to add any value and it introduces a lot of fragility to the auto-improvement loop. 