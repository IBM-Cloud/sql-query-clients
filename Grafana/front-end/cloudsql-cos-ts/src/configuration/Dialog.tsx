import React from 'react';
import { Button, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions } from '@material-ui/core';
import { DataSourceInstanceSettings } from '@grafana/data';

import { COSIBMDataSourceOptions } from '../types';

export function AlertDialog(props: DataSourceInstanceSettings<COSIBMDataSourceOptions>) {
  const [open, setOpen] = React.useState(false);

  const handleClickOpen = () => {
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
  };

  return (
    <>
      <div>
        <Button variant="outlined" color="primary" onClick={handleClickOpen}>
          Open alert dialog
        </Button>
        <Dialog
          open={open}
          onClose={handleClose}
          aria-labelledby="alert-dialog-title"
          aria-describedby="alert-dialog-description"
        >
          <DialogTitle id="alert-dialog-title">{'Datasource setting info'}</DialogTitle>
          <DialogContent>
            <DialogContentText id="alert-dialog-description">
              URL {props.url} API Key {props.jsonData.apiKey}
              CRN {props.jsonData.instance_crn}
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleClose} color="primary">
              Disagree
            </Button>
            <Button onClick={handleClose} color="primary" autoFocus>
              Agree
            </Button>
          </DialogActions>
        </Dialog>
      </div>
    </>
  );
}
