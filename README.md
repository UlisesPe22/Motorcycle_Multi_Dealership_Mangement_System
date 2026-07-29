# Motorcycle Dealership Mangement System
**This mangement system is grounded on a real-world collaboration with a motorcycle dealership group operating multiple retail locations in Mexico.** The organization’s operations cover the full commercial lifecycle of a motorcycle. Starting by purchasing the motorcycles to a national distributor, followed by inventory management across multiple locations, to the final retail sale and commission settlement with sales personnel.

- [System Architecture Design](#system-architecture-design)
- [Unstructured Data Processing for Inventory Management and Client Registration](#unstructured-data-processing-for-inventory-mangement-and-client-registration-with-)
  - [Data Processing for Automatic Inventory Management](#data-processing-for-automatic-inventory-mangement)
- [Overview of Additional Functions (Full Stack Application)](#overview-of-additional-functions-full-stack-application))
- [Performance Test](#performance-test)

**The mangment system is too large to cover it in a single readme file. Therefore, only the most significant functionalities will be detailed here.**

# System Architecture Design
The architectural design was built to run locally during development but thought to easily migrate to a cloud deployment environment. For this reason, the system adopts containerization with ![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white). 

<div align="center">

<img src="https://raw.githubusercontent.com/UlisesPe22/Motorcycle_Multi_Dealership_Mangement_System/main/photos_readme/system_architecture"/>

</div>

The system is separated into three main modules, each running inside its own Docker container controlled by Docker Compose. The user interacts with the frontend container via HTTP. The frontend is built with the ![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB) and compiled by ![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white). The frontend communicates with the backend container using REST API architecture and sending requests to ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
endpoints. The backend logic is written in ![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white). Some pipelines make requests to the Gemini API using an API key stored as an environment variable. The backend communicates with the ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white) database container through ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white).



# Unstructured Data Processing for Inventory Mangement and Client Registration with ![Google Gemini](https://img.shields.io/badge/Google%20Gemini-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)

The business operations produce sevral artifacts of unstructred data such as PDFs or images. This section will explain how the analysis and extraction of data from this artifacts produces an inventory mangement tool.

**All piplines that extract data out of unstructured documents follow roughly this logic**
![Data Extraction Process](https://raw.githubusercontent.com/UlisesPe22/Motorcycle_Multi_Dealership_Mangement_System/main/photos_readme/data_extraction_process)

## Data Processing for Automatic Inventory Mangement
Currenlty the company mantains many versions of the inventory manually in excel sheets. This is extremly time consuming and causes many economical problemns since teh owner is never able to know the current stock of motorcycles or if the motorcycles she ordered, actully got delivered. This software provides a solution to have a unified inventory that is easy to mantain and reliable. The process will be summerized in the video and explained in the next paragraphs:

![Inventory Process Demo](photos_readme/Inventory_process.gif)

### First document in the lifecycle which is produced when the owner buys any amount of motorcycles to the distributor.

From this document I extract the PDF embedded text and since it may have changes in the order of the information, I use Gemini as a sophisitcated parser and I constrain its repsonse to only output text that is in the input text. Moreover I add a deterministic function to verfify the response. These measures make the probabilistic nature of LLMs not a risk for Data Integrity.

<div align="center">

<img src="https://raw.githubusercontent.com/UlisesPe22/Motorcycle_Multi_Dealership_Mangement_System/main/photos_readme/purchase_document"/>

</div>
Here we extract the distributor's codes which are known beforehand and the quantity column. For every motorcycle purchase a new row is created in the inventory and the status of these new rows are "Purchased". 

### Second Event and second document. 
The distributor sends an email with a PDF where we get the motorcycles series numbers and color after some time. This document purpose is to notify that the motorcycles are in transit and will get arrive soon.

<div align="center">

<img src="https://raw.githubusercontent.com/UlisesPe22/Motorcycle_Multi_Dealership_Mangement_System/main/photos_readme/in_transit_document.png"/>

</div>

From this document, we match the motorcycles that were captured in the first document and we asign color and series number to them, moreover, we transition it to a different status "incoming". 

### Final Event -- Physical delivery 
This event produces a different artifact that we analyse. Is a scanned picutre that has the infomration of the motorcycles that arrived. We match this information with the motorcycles marked as "incoming" and if the series numbers concide, then the motorcycle transtiosn to "in_stock". 

<div align="center">

<img src="https://raw.githubusercontent.com/UlisesPe22/Motorcycle_Multi_Dealership_Mangement_System/main/photos_readme/delivery_document"/>

</div>

# Overview of Additonal Functions (Full Stack Application)
This software mangement tool covers multiple business functions and events. It is not possible to detail all here, nevertheless the next video is meant for the reader to see more details and functions of the system which covers all the Prodcut Lifecycle. All of this featrues are more web development oriented.

![Additional Functions Demo](photos_readme/additional_functions.gif)

# Performance Test
The system was initially developed with synchronous endpoints and later fully migrated to asynchronous programming. Load tests conducted with Locust demonstrated a significant reduction in response time and a measurable increase in concurrent user capacity under the same hardware conditions. **The image below are the results of the Async Version. On the left side we see a load test with 50 simultaneously active users and in the right side with 100 users.**

<div align="center">

<img src="https://raw.githubusercontent.com/UlisesPe22/Motorcycle_Multi_Dealership_Mangement_System/main/photos_readme/user_tests"/>

</div>
