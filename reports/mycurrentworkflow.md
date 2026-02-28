This is a summary of my current workflow. The general explanation can be found in the README.md file. The paths are referenced in the paths.md file.

My main workspace are the jupyter notebooks located in the notebooks directory. I use this to explore the data, do experimental modifications, perform analysis, and visualize the results. However, this results in a very messy and confusing workflow.

The first thing I do is import my data in the windows directory. And then I import them in the notebooks using python import commands. I have a script for the data processing called data_loader.py. And then I view the data structure using various print commands, and also the data wrangler extention. Then I perform data cleaning based on the type of analysis I want to perform. Then I perform the analysis and visualization in the notebooks. Based on the results, I adjusted the data cleaning process, and repeat the process until I get the desired results. During this discovery process, I constantly modify the data cleaning process and analysis steps by consulting with AI agent along the way. I ask things such as alternative ways to perform the analysis, and improvements to the code.

The problem is that whenever I want to conduct a new analysis, there's a lot of manual steps that I have to repeat. What I want now is to automate all of the pipelines that have been well established in my workflow so I don't have to do it manually every time I want to conduct a new analysis in the future.

I want you to identify all of these steps in my workflow. Then I want you to give me suggestions for the steps that can be optimized or automated. Either in a form of a python script, shell script, or any other form of automation that you think is appropriate. Also consider the option of automation using the AI agent functionality by creating an agent workflow or skills to automate tasks.

I also want to be able to integrate the results of my data cleaning and analysis back into a main dataset. This way if I make any modifications to any of the steps in the data cleaning process or analysis, I can seamlessly update the main dataset without having to manually update it in each of the succeeding notebooks or scripts. Give me suggestions for the best way to implement this in my workflow.

As I perform further analysis, I also find things that I want to change in the data cleaning process or analysis from time to time. And if these modifications happens in the main dataset or somewhere along the preceeding data cleaning or analysis process, it will have an effect on all the succeeding analysis steps. Which means I have to manually look through all the previous steps again to apply this modifications. This is very time consuming and inefficient.

Furthermore, if I conduct the analysis pipeline again with a modified dataset or analysis steps, the resulting output will be different from the previous one. This is not a problem if I'm just conducting the analysis once. But if I'm conducting the analysis multiple times, it will be a problem. Because I need to keep track of all the different outputs and compare them with each other, as well as organize them in a way that I can easily access them later on.

I want to create a standardized analysis pipeline that similar to the commonly used pipelines in the data science field.

The naming conventions of the files and variables in the notebook area also inconsistent.

I want to creata an agent skill/workflow to turn a finalized notebook into a python script that can be run in the terminal.