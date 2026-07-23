# Overview
This mangement system is grounded on a real-world collaboration with a motorcycle dealership group operating multiple retail locations in Mexico. The organization’s operations cover the full commercial lifecycle of a motorcycle. Starting by purchasing the motorcycles to a national distributor, followed by inventory management across multiple locations, to the final retail sale and commission settlement with sales personnel.
**The mangment system is too large to cover it in a single readme file. Therefore, only the most significant functionalities will be detailed here

# Unstructured Data Processing for Inventory Mangement and Client Registration
The business operations produce sevral artifacts of unstructred data such as PDFs or images. This section will explain how the analysis and extraction of dta from this artifacts produces valuable tools for business events.

**All piplines that extract data out of unstructured documents follow roughly this logic**


## Data Extraction of National Identity Documents with Gemini 3.1 lite
The aim of this module is to extract the necessary information out of Mexican National ID. We collect the information we need to create a future sale contract. This method improves teh company current approach since the sale personel manually fills all information into a contract. The latter is time consumiing and produces multiple typing erros.

### Phase 1 -- Document detection and corner extraction 
The first phase main goal capturing the spatial points that make the four corners of the ID card rectangle and validating the data; this process produces one Gemini call per side. Each call returns the four corner coordinates of the card within the image and validate the image is an actual ID and not just the image of a puppy.

### Phase 2 -- Field extraction 
Each side is processed by a different prompt. Gemini receives the original  image alongside the corner coordinates related to the image and is asked to extract specific infomation.

## Data Processing for Automatic Inventory Mangement
Currenlty the company mantains many versions of the inventory manually in excel sheets. This is extremly time consuming and causes many economical problemns since teh owner is never able to know the current stock of motorcycles or if the motorcycles she ordered, actully got delivered. This software provides a solution to have a unified inventory that is easy to mantain and reliable.

### First document in the lifecycle which is produced when the owner buys any amount of motorcycles to the distributor.

From this document I extract the PDF embedded text and since it may have changes in the order of the information, I use Gemini as a sophisitcated parser and i constrain its repsonse to only output text that is in the input text. Moreover I add a deterministic function to verfify the response. These measures make the probabilistic nature of LLMs not a risk for the process.

Here we extract the distributor's codes which are known beforehand and the quantity column. For every motorcycle purchase a new row is created in the inventory and the status of these new rows are "Purchased". 

### Second Event and second document. 
The distributor sends an email with a PDF where we get the motorcycles series numbers and color. This document purpose is to notify that the motorcycles are in transit and will get arrive soon.

From this document, we match the motorcycles that were captured in the first document and we asign color and series number to them, moreover, we transition it to a different status "incoming". 

### Final Event -- Physical delivery 
This event produces a differetn artifact that we analyse. Is a scanned picutre that has the infomration of the motorcycles that arrived. We match this information with the motorcycles marked as "incoming" and if the series numbers concide, then the motorcycle transtiosn to "in_stock". 
