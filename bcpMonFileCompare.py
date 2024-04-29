import mysql.connector
import subprocess
from datetime import datetime
import os

DATE_FOLDER = datetime.now().strftime("%Y-%m-%d")

def connectToDatabase():
    return mysql.connector.connect(
        host="localhost",
        user="bcp_grafana",
        password="bcp_Grafana@123",
        database="bcp_grafana"
    )

def fetchFromDatabase(sql_query):
    database = connectToDatabase()
    dbcursor = database.cursor()
    dbcursor.execute(sql_query)
    output = dbcursor.fetchall()
    database.close() 
    
    return output

def checkExtFileAvailability(extensions, username, serverIP, serverPath):
    exensionString = ""
    for extension in extensions.split(","):
        print(f"INFO: Looking for files with {extension} extension, on {serverIP} in {serverPath} path.")
        LINUX_COMMAND = f'''ssh {username}@{serverIP}  "cd {serverPath} && ls *.{extension}"'''
        try:
            COMMAND_OUTPUT = subprocess.check_output(LINUX_COMMAND, shell=True, stderr=subprocess.STDOUT)
            OUTPUT_AS_LIST = COMMAND_OUTPUT.decode('utf-8').split("\n")
            exensionString = exensionString + "*." + extension + " "
        except subprocess.CalledProcessError as e:
            if e.returncode == 2:
                print(f"Warning: No files found with {extension} extension, on {serverIP} in {serverPath} path.")
            else:
                print(f"Error: Failed to execute the listing Command on {serverIP} server.")
    
    return exensionString

def getLocalServerMD5Sum(localServerPath, extensions, localServerIP, localUsername, projectName):
    
    LOCAL_MD5SUM_HASH = {}
    if extensions == "Any":
        LINUX_COMMAND = f'''ssh {localUsername}@{localServerIP}  "cd {localServerPath} && md5sum *"'''
    else:
        exensionString = checkExtFileAvailability(extensions, localUsername, localServerIP, localServerPath)
        LINUX_COMMAND = f'''ssh {localUsername}@{localServerIP}  "cd {localServerPath} && md5sum {exensionString}"'''
        
    try:
        COMMAND_OUTPUT = subprocess.check_output(LINUX_COMMAND, shell=True, stderr=subprocess.STDOUT)

        print(f"INFO: Gathering MD5SUM - Project({projectName}) - IP({localServerIP}) - Path({localServerPath})")
                
        OUTPUT_AS_LIST = COMMAND_OUTPUT.decode('utf-8').split("\n")
        
        OUTPUT_AS_LIST = list(filter(bool, OUTPUT_AS_LIST))

        for resultLine in OUTPUT_AS_LIST:
            
            values = resultLine.split()
            key = values[1]
            value = values[0]

            LOCAL_MD5SUM_HASH[key] = value
        
        return LOCAL_MD5SUM_HASH
        
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")

def getBCPServerMD5Sum(bcpServerPath, extensions, BCPServerIP, BCPUsername, projectName):
    
    BCP_MD5SUM_HASH = {}
    if extensions == "Any":
        LINUX_COMMAND = f'''ssh {BCPUsername}@{BCPServerIP}  "cd {bcpServerPath} && md5sum *"'''
    else:
        exensionString = checkExtFileAvailability(extensions, BCPUsername, BCPServerIP, bcpServerPath)
        LINUX_COMMAND = f'''ssh {BCPUsername}@{BCPServerIP}  "cd {bcpServerPath} && md5sum {exensionString}"'''
            
    try:
        COMMAND_OUTPUT = subprocess.check_output(LINUX_COMMAND, shell=True, stderr=subprocess.STDOUT)

        print(f"INFO: Gathering - Project({projectName}) - IP({BCPServerIP}) - Path({bcpServerPath})")
                    
        OUTPUT_AS_LIST = COMMAND_OUTPUT.decode('utf-8').split("\n")
        
        OUTPUT_AS_LIST = list(filter(bool, OUTPUT_AS_LIST))

        for resultLine in OUTPUT_AS_LIST:
            
            values = resultLine.split()
            key = values[1]
            value = values[0]

            BCP_MD5SUM_HASH[key] = value
        
        return BCP_MD5SUM_HASH
        
    except subprocess.CalledProcessError as e:
        print(f"Error: Information gathering command executing is failed {e}")

def getRuleID():
    
    SYNC_STATUS = "Success"
    
    checkedRulesList = []

    with open(".cache/checkedRules", 'r') as checkedRules:
        for checkedRule in checkedRules:
            checkedRulesList.append(int(checkedRule.strip()))
    
    sql_query = """ 
        select * from bcpSyncRules
    """
    rulesInfo = fetchFromDatabase(sql_query)
    
    for ruleInfo in rulesInfo:
        print(ruleInfo)
        print("-"*90)
        print("INFO: Starting rule ID - " + str(ruleInfo[0]) + " " + str(ruleInfo[-1]))

        if int(ruleInfo[0]) in checkedRulesList:
            print(f"INFO: Skipping rule ID - {ruleInfo[0]}.")

        else:
            projectName = ruleInfo[1]
            localServerPath = ruleInfo[2]
            bcpServerPath = ruleInfo[3]
            serversID = ruleInfo[4]
            extensions = ruleInfo[5]
            alias = ruleInfo[6]
            
            print("INFO: Servers ID - " + str(ruleInfo[4]))
            
            sql_query = f""" 
                select * from bcpServerDetails where serversID = "{serversID}"
            """
            serversInfo = fetchFromDatabase(sql_query)
            
            localServerIP = serversInfo[0][2]
            localUsername = serversInfo[0][3]
            BCPServerIP = serversInfo[0][4]
            BCPUsername = serversInfo[0][5]
            
            LOCAL_MD5SUM_HASH = getLocalServerMD5Sum(localServerPath, extensions, localServerIP, localUsername, projectName)
            BCP_MD5SUM_HASH = getBCPServerMD5Sum(bcpServerPath, extensions, BCPServerIP, BCPUsername, projectName)
            try:
                for key, value in LOCAL_MD5SUM_HASH.items():
                    if key in BCP_MD5SUM_HASH:
                        if value == BCP_MD5SUM_HASH[key]:
                            print(f"INFO: File {key} is same on the both servers.")
                        else:
                            print(f"Warning: File {key} is not same on the both servers.")
                            SYNC_STATUS = "Failed"        
                    else:
                        print(f"Warning: File {key} was not found in BCP Enviorment.")
                        SYNC_STATUS = "Failed"
                
                if not os.path.exists("DATA/" + DATE_FOLDER):
                    try:
                        os.makedirs("DATA/" + DATE_FOLDER)
                        print(f"INFO: {DATE_FOLDER} folder has been created successfully.")
                    except:
                        print("Error: Unable to create the DATA/" + DATE_FOLDER)
                    
                with open("DATA/" + DATE_FOLDER + "/" +  projectName, 'a') as projectFile:
                    projectFile.write(f"{alias},{SYNC_STATUS}\n")
                with open(".cache/checkedRules", 'a') as checkedRules:
                    checkedRules.write("\n"+str(ruleInfo[0]))
            except:
                print("Error: The server did not return data for given extensions.") 
            print("-"*90)    

        
def main():
    getRuleID()
    
if __name__ == "__main__":
    main()
