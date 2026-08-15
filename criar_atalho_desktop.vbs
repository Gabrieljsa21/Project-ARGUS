' Cria o atalho "Argus" na Area de Trabalho do usuario atual, apontando pra
' iniciar_argus_oculto.vbs NESTA MESMA PASTA - onde quer que o projeto tenha sido
' clonado (usa WshShell.SpecialFolders("Desktop"), que ja resolve certo mesmo com a
' Area de Trabalho redirecionada pro OneDrive). Roda uma vez so, depois de clonar o
' repositorio - da pra rodar de novo sem problema (so sobrescreve o atalho).

Set oWshShell = CreateObject("WScript.Shell")
Set oFso = CreateObject("Scripting.FileSystemObject")

strPastaAtual = oFso.GetParentFolderName(WScript.ScriptFullName)
strDesktop = oWshShell.SpecialFolders("Desktop")

Set oAtalho = oWshShell.CreateShortcut(strDesktop & "\Argus.lnk")
oAtalho.TargetPath = strPastaAtual & "\iniciar_argus_oculto.vbs"
oAtalho.WorkingDirectory = strPastaAtual
oAtalho.Description = "Iniciar Argus (widget de chamados do Jira)"

strIcone = strPastaAtual & "\assets\argus.ico"
If oFso.FileExists(strIcone) Then
    oAtalho.IconLocation = strIcone
End If

oAtalho.Save

MsgBox "Atalho ""Argus"" criado na sua Area de Trabalho!", vbInformation, "Argus"
